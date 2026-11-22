"""Small provider-neutral port; an SDK/HTTP adapter supplies an async generate callable."""
import copy
import inspect


class ProviderAdapter:
    """No provider selection, credentials, network access or automatic fallback here.

    generate receives keyword arguments: messages, output_schema, max_output_tokens,
    deadline_at. It returns one JSON string. Image blocks contain base64 bytes,
    never paths/URLs. A future provider adapter translates these blocks to its SDK.
    It must cooperate with asyncio cancellation and must not run blocking I/O.
    """

    def __init__(self, model_config_version, generate):
        if not isinstance(model_config_version, str) or not model_config_version.strip():
            raise ValueError("A versioned model configuration is required")
        if not callable(generate) or not (inspect.iscoroutinefunction(generate)
                                          or inspect.iscoroutinefunction(getattr(generate, "__call__", None))):
            raise ValueError("Provider generate must be an async callable")
        self.model_config_version = model_config_version
        self._generate = generate

    async def complete(self, messages, output_schema, deadline_at):
        return await self._generate(messages=copy.deepcopy(messages), output_schema=copy.deepcopy(output_schema),
                                    max_output_tokens=2048, deadline_at=deadline_at)
