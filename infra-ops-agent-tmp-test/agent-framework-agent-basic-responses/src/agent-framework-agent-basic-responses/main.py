# Copyright (c) Microsoft. All rights reserved.

from __future__ import annotations

import os

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from ops_agent.agents.definitions import ORCHESTRATOR_INSTRUCTIONS
from ops_agent.tools import hosted_tools

load_dotenv()

# Register hosted tools with Foundry Agent Framework
investigate_incident = tool(approval_mode="never_require")(hosted_tools.investigate_incident)
get_azure_resource_health = tool(approval_mode="never_require")(hosted_tools.get_azure_resource_health)
query_log_analytics = tool(approval_mode="never_require")(hosted_tools.query_log_analytics)
predict_vm_failure = tool(approval_mode="never_require")(hosted_tools.predict_vm_failure)
predict_endpoint_incident = tool(approval_mode="never_require")(hosted_tools.predict_endpoint_incident)
get_approved_runbook = tool(approval_mode="never_require")(hosted_tools.get_approved_runbook)
list_registered_tools = tool(approval_mode="never_require")(hosted_tools.list_registered_tools)


def _project_endpoint() -> str:
    return (
        os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        or os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        or ""
    )


def main() -> None:
    model_name = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME")
    endpoint = _project_endpoint()
    if not model_name:
        raise RuntimeError("Set AZURE_AI_MODEL_DEPLOYMENT_NAME or FOUNDRY_MODEL_NAME")
    if not endpoint:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT or AZURE_AI_PROJECT_ENDPOINT")

    os.environ.setdefault("OPS_AGENT_DATA_MODE", os.getenv("OPS_AGENT_DATA_MODE", "mock"))

    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model_name,
        credential=DefaultAzureCredential(),
    )

    agent = Agent(
        client=client,
        name="infra-ops-agent",
        instructions=ORCHESTRATOR_INSTRUCTIONS
        + """

When the user asks to investigate an incident, device, VM, or alert:
1. Prefer calling investigate_incident(resource, user_report) for the full governed workflow.
2. Use individual tools only when a partial data request is explicitly needed.
3. Return the Required Agent Response Format from workflow output when available.
4. Never invent telemetry, ServiceNow numbers, or ML probabilities.
""",
        tools=[
            investigate_incident,
            get_azure_resource_health,
            query_log_analytics,
            predict_vm_failure,
            predict_endpoint_incident,
            get_approved_runbook,
            list_registered_tools,
        ],
        default_options={"store": False},
    )

    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
