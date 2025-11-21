from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.llm_model import generate_text


app = FastAPI(title="Opportunity Center Chat Backend", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    id: str
    content: str
    role: Literal["user", "assistant"]
    timestamp: str
    conversationId: str


class SendMessageRequest(BaseModel):
    message: str
    conversationId: Optional[str] = None


class SendMessageResponse(BaseModel):
    message: ChatMessage
    conversationId: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messageCount: int


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]
    conversationId: str

# --- Data ---

conversation_messages: dict[str, list[ChatMessage]] = {}
conversation_metadata: dict[str, dict[str, datetime | str]] = {}

def _derive_title(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "New Conversation"
    return cleaned[:60] + ("..." if len(cleaned) > 60 else "")


def _create_conversation(first_user_message: str) -> str:
    conv_id = str(uuid4())
    now = datetime.utcnow()
    conversation_metadata[conv_id] = {
        "title": _derive_title(first_user_message),
        "created_at": now,
        "updated_at": now,
    }
    conversation_messages[conv_id] = []
    return conv_id


def _ensure_conversation(conversation_id: Optional[str], user_message: str) -> str:
    if conversation_id and conversation_id in conversation_metadata:
        return conversation_id
    return _create_conversation(user_message)


def _store_message(
    conversation_id: str, role: Literal["user", "assistant"], content: str
) -> ChatMessage:
    if conversation_id not in conversation_messages:
        now = datetime.utcnow()
        conversation_messages[conversation_id] = []
        conversation_metadata[conversation_id] = {
            "title": "New Conversation",
            "created_at": now,
            "updated_at": now,
        }

    message = ChatMessage(
        id=str(uuid4()),
        content=content,
        role=role,
        timestamp=datetime.utcnow().isoformat(),
        conversationId=conversation_id,
    )
    conversation_messages[conversation_id].append(message)

    meta = conversation_metadata[conversation_id]
    meta["updated_at"] = datetime.utcnow()
    if role == "user" and (not meta.get("title") or meta["title"] == "New Conversation"):
        meta["title"] = _derive_title(content)

    return message


def _build_prompt(conversation_id: str) -> str:
    history = conversation_messages.get(conversation_id, [])
    recent_history = history[-10:]

    latest_user = next(
        (msg for msg in reversed(recent_history) if msg.role == "user"), None
    )

    history_lines = []
    for msg in recent_history:
        role = "User" if msg.role == "user" else "Assistant"
        history_lines.append(f"{role}: {msg.content}")
    history_block = "\n".join(history_lines)

    if not latest_user:
        latest_content = ""
    else:
        latest_content = latest_user.content

    system = (
        "You are a helpful assistant for the Opportunity Center. "
        "Provide a single concise answer to the most recent user question. "
        "Do not invent or ask questions. Reply with only the answer text, no prefixes or labels. "
        "Keep replies under 80 words."
    )

    return (
        f"{system}\n\n"
        f"Recent conversation:\n{history_block}\n\n"
        f"Answer the latest user question once. Do not add new questions.\n"
        f"Latest question: {latest_content}\n"
        f"Answer:"
    )


def _conversation_summary(conversation_id: str) -> ConversationSummary:
    meta = conversation_metadata[conversation_id]
    messages = conversation_messages.get(conversation_id, [])

    title = meta.get("title", "New Conversation")
    if (not title or title == "New Conversation") and messages:
        for msg in messages:
            if msg.role == "user":
                title = _derive_title(msg.content)
                break

    return ConversationSummary(
        id=conversation_id,
        title=title or "Conversation",
        createdAt=meta["created_at"].isoformat(),
        updatedAt=meta["updated_at"].isoformat(),
        messageCount=len(messages),
    )

# --- Endpoints ---

@app.get("/")
async def root():
    return {"message": "Opportunity Center Chat API", "status": "ok"}


@app.get("/api/chat/conversations", response_model=List[ConversationSummary])
def list_conversations():
    summaries = [_conversation_summary(conv_id) for conv_id in conversation_metadata]
    summaries.sort(key=lambda s: s.updatedAt, reverse=True)
    return summaries


@app.get("/api/chat/conversations/{conversation_id}", response_model=ChatHistoryResponse)
def get_conversation(conversation_id: str):
    if conversation_id not in conversation_messages:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return ChatHistoryResponse(
        messages=conversation_messages[conversation_id],
        conversationId=conversation_id,
    )


@app.post("/api/chat/message", response_model=SendMessageResponse)
def chat_with_llm(req: SendMessageRequest):
    message_text = req.message.strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="Message must not be empty.")

    conversation_id = _ensure_conversation(req.conversationId, message_text)

    # Add the user message to history before calling the model
    _store_message(conversation_id, "user", message_text)

    prompt = _build_prompt(conversation_id)

    try:
        reply_text = generate_text(
            prompt=prompt,
            max_new_tokens=80,
            temperature=0.2,
            top_p=0.8,
            do_sample=False,
            wrap_prompt=False,
            strip_after="Answer:",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="LLM generation failed.")

    assistant_message = _store_message(conversation_id, "assistant", reply_text)

    return SendMessageResponse(
        message=assistant_message,
        conversationId=conversation_id,
    )


@app.delete("/api/chat/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    if conversation_id not in conversation_metadata:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conversation_metadata.pop(conversation_id, None)
    conversation_messages.pop(conversation_id, None)
    return {"message": "Conversation deleted."}


@app.delete("/api/chat/conversations/{conversation_id}/messages")
def clear_conversation_messages(conversation_id: str):
    if conversation_id not in conversation_metadata:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conversation_messages[conversation_id] = []
    conversation_metadata[conversation_id]["updated_at"] = datetime.utcnow()
    return {"message": "Conversation messages cleared."}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
