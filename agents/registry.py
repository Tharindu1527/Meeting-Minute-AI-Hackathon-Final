# agents/registry.py


class AgentRegistry:
    """
    Registry for meeting analysis agents

    Agent classes register themselves with @register_agent. `create` returns a
    fresh instance each time: CrewAI agents hold per-run state, so sharing one
    instance between concurrent analyses (e.g. two users) is not safe.
    """

    def __init__(self):
        """Initialize the agent registry"""
        self.agent_classes = {}
        self.default_model = None  # None: agents fall back to GEMINI_MODEL

    def register(self, agent_id, agent_class):
        """
        Register an agent class

        Args:
            agent_id (str): Unique identifier for the agent
            agent_class (class): Agent class extending BaseAgent
        """
        self.agent_classes[agent_id] = agent_class

    def create(self, agent_id, model=None):
        """
        Create an agent instance

        Args:
            agent_id (str): Agent identifier
            model (str, optional): Model to use for this agent

        Returns:
            BaseAgent: New agent instance
        """
        if agent_id not in self.agent_classes:
            raise ValueError(f"Agent '{agent_id}' not registered. Available: {sorted(self.agent_classes)}")
        return self.agent_classes[agent_id](model=model or self.default_model)

    def set_default_model(self, model):
        self.default_model = model


# Global registry instance
registry = AgentRegistry()


def register_agent(agent_id):
    """
    Decorator to register an agent class with the registry

    Args:
        agent_id (str): Unique identifier for the agent
    """
    def decorator(agent_class):
        registry.register(agent_id, agent_class)
        return agent_class
    return decorator


def get_agent(agent_id, model=None):
    """
    Create an agent instance from the registry

    Args:
        agent_id (str): Agent identifier
        model (str, optional): Model to use

    Returns:
        BaseAgent: New agent instance
    """
    return registry.create(agent_id, model)


def list_agents():
    return sorted(registry.agent_classes)


def set_default_model(model):
    """Set the model used when none is given"""
    registry.set_default_model(model)
