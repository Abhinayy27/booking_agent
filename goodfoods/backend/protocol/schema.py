import uuid
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class AgentCard(BaseModel):
    """
    Defines the capabilities and identity of an agent in the network.
    """
    id: str
    name: str
    description: str
    capabilities: List[str]
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"

class Task(BaseModel):
    """
    A unit of work to be executed by an agent.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent_id: str
    target_agent_id: str
    intent: str
    input_data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)

class Artifact(BaseModel):
    """
    The result produced by an agent after executing a task.
    """
    task_id: str
    producer_agent_id: str
    status: Literal["success", "failure", "pending"]
    data: Any
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class Message(BaseModel):
    """
    A message wrapper for communication between agents (or user and agent).
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: str
    content: str
    task: Optional[Task] = None
    artifact: Optional[Artifact] = None
    timestamp: datetime = Field(default_factory=datetime.now)
