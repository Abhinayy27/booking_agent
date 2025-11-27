import json
from typing import List, Optional
from backend.protocol.schema import AgentCard

class AgentRegistry:
    def __init__(self, registry_path: str = "backend/agent_registry.json"):
        self.registry_path = registry_path
        self.agents: List[AgentCard] = []
        self._load_registry()

    def _load_registry(self):
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                self.agents = [AgentCard(**agent) for agent in data]
        except FileNotFoundError:
            self.agents = []
        except Exception as e:
            print(f"Error loading registry: {e}")
            self.agents = []

    def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def find_agents_by_capability(self, capability: str) -> List[AgentCard]:
        return [agent for agent in self.agents if capability in agent.capabilities]

    def list_all_agents(self) -> List[AgentCard]:
        return self.agents
