"""
MinIO-based Conversation History Storage
Stores user conversations and chat history in self-hosted MinIO.
Each user has their own bucket/prefix for organized storage.
"""
from __future__ import annotations
import json
import structlog
from datetime import datetime
from typing import Optional
from minio import Minio
from minio.error import S3Error

from backend.config import settings

log = structlog.get_logger(__name__)


class MinioConversationStore:
    """Store and retrieve conversation history using MinIO object storage."""

    def __init__(self):
        self.enabled = bool(settings.minio_endpoint and settings.minio_access_key)
        self.client: Optional[Minio] = None
        self.bucket_name = settings.minio_bucket_name or "analytics-copilot-conversations"

        if self.enabled:
            self._connect()

    def _connect(self):
        """Initialize MinIO client and ensure bucket exists."""
        try:
            self.client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )

            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                log.info("minio.bucket_created", bucket=self.bucket_name)

            log.info("minio.connected", endpoint=settings.minio_endpoint)
        except Exception as e:
            log.error("minio.connection_failed", error=str(e))
            self.enabled = False
            self.client = None

    def _get_object_path(self, user_id: str, conversation_id: str) -> str:
        """Generate object path for a conversation."""
        return f"users/{user_id}/conversations/{conversation_id}.json"

    def _get_session_path(self, user_id: str, session_id: str) -> str:
        """Generate object path for a session."""
        return f"users/{user_id}/sessions/{session_id}.json"

    def save_conversation(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        response: dict,
        session_id: str = None,
    ) -> bool:
        """
        Save a conversation turn (question + response) to MinIO.
        Appends to existing conversation or creates new.
        """
        if not self.enabled or not self.client:
            return False

        try:
            # Load existing conversation
            path = self._get_object_path(user_id, conversation_id)
            conversation = self._load_json(path)

            if conversation is None:
                conversation = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "messages": [],
                }

            # Add new message
            conversation["messages"].append({
                "role": "user",
                "content": question,
                "timestamp": datetime.utcnow().isoformat(),
            })
            conversation["messages"].append({
                "role": "assistant",
                "content": response.get("text", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "sql": response.get("sql", ""),
                    "row_count": response.get("row_count", 0),
                    "viz_type": response.get("viz_type"),
                },
            })
            conversation["updated_at"] = datetime.utcnow().isoformat()

            # Save back to MinIO
            data = json.dumps(conversation, indent=2).encode("utf-8")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=path,
                data=data,
                length=len(data),
                content_type="application/json",
            )

            log.debug("minio.conversation_saved",
                     user_id=user_id,
                     conversation_id=conversation_id,
                     messages=len(conversation["messages"]))
            return True

        except Exception as e:
            log.error("minio.save_conversation_failed", error=str(e))
            return False

    def get_conversation_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Retrieve conversation history for a user.
        Returns list of messages in LangChain format.
        """
        if not self.enabled or not self.client:
            return []

        try:
            path = self._get_object_path(user_id, conversation_id)
            conversation = self._load_json(path)

            if not conversation:
                return []

            messages = conversation.get("messages", [])[-limit:]
            return [{"role": m["role"], "content": m["content"]} for m in messages]

        except Exception as e:
            log.error("minio.get_history_failed", error=str(e))
            return []

    def _load_json(self, path: str) -> Optional[dict]:
        """Load JSON object from MinIO."""
        try:
            response = self.client.get_object(self.bucket_name, path)
            data = response.read()
            return json.loads(data.decode("utf-8"))
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            raise
        except Exception:
            return None

    def list_user_conversations(self, user_id: str) -> list[dict]:
        """List all conversations for a user."""
        if not self.enabled or not self.client:
            return []

        try:
            prefix = f"users/{user_id}/conversations/"
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
            )

            conversations = []
            for obj in objects:
                # Extract conversation_id from path
                conv_id = obj.object_name.replace(prefix, "").replace(".json", "")
                metadata = self._load_json(obj.object_name)
                if metadata:
                    conversations.append({
                        "conversation_id": conv_id,
                        "created_at": metadata.get("created_at"),
                        "updated_at": metadata.get("updated_at"),
                        "message_count": len(metadata.get("messages", [])),
                    })

            return sorted(conversations, key=lambda x: x["updated_at"], reverse=True)

        except Exception as e:
            log.error("minio.list_conversations_failed", error=str(e))
            return []

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a specific conversation."""
        if not self.enabled or not self.client:
            return False

        try:
            path = self._get_object_path(user_id, conversation_id)
            self.client.remove_object(self.bucket_name, path)
            log.info("minio.conversation_deleted", user_id=user_id, conversation_id=conversation_id)
            return True
        except Exception as e:
            log.error("minio.delete_failed", error=str(e))
            return False


# Singleton instance
minio_conversation_store = MinioConversationStore()
