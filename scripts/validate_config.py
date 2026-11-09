
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOOLS = {
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}


class CompetitionLoader(yaml.SafeLoader):
    pass


def include_file(loader, node):
    relative_path = (
        Path(loader.name).parent / loader.construct_scalar(node)
    )

    resolved_path = relative_path.resolve()

    if not resolved_path.is_relative_to(ROOT):
        raise ValueError(
            f"Include path outside project: {resolved_path}"
        )

    if not resolved_path.is_file():
        raise FileNotFoundError(
            f"Included file not found: {resolved_path}"
        )

    return resolved_path.read_text(encoding="utf-8")


CompetitionLoader.add_constructor("!include", include_file)


def load_config(path):
    with path.open(encoding="utf-8") as file:
        return yaml.load(file, Loader=CompetitionLoader)


def validate_agent(path, expected_tools=None):
    config = load_config(path)

    assert isinstance(config, dict), (
        f"Invalid agent config: {path}"
    )

    assert config.get("name"), (
        f"Missing agent name: {path}"
    )

    assert config.get("model"), (
        f"Missing agent model: {path}"
    )

    assert config.get("instruction"), (
        f"Instruction not loaded: {path}"
    )

    tools = config.get("tools", [])

    assert isinstance(tools, list), (
        f"Tools must be a list: {path}"
    )

    normal_tools = set()
    agent_tool_paths = set()

    for tool in tools:

        if isinstance(tool, str):
            normal_tools.add(tool)

        elif isinstance(tool, dict):

            assert set(tool.keys()) == {"agent_tool"}, (
                f"Invalid tool dictionary in {path}: {tool}"
            )

            agent_tool = tool["agent_tool"]

            assert isinstance(agent_tool, dict), (
                f"agent_tool must be a dictionary: {path}"
            )

            config_path = agent_tool.get("config_path")

            assert config_path, (
                f"Missing agent_tool config_path: {path}"
            )

            assert agent_tool.get("skip_summarization") is True, (
                f"skip_summarization must be true: {path}"
            )

            resolved_path = (
                path.parent / config_path
            ).resolve()

            assert resolved_path.is_relative_to(ROOT), (
                f"AgentTool path outside project: {resolved_path}"
            )

            assert resolved_path.is_file(), (
                f"AgentTool config not found: {resolved_path}"
            )

            agent_tool_paths.add(config_path)

        else:
            raise ValueError(
                f"Unsupported tool format in {path}: {tool}"
            )

    unknown_tools = normal_tools - ALLOWED_TOOLS

    assert not unknown_tools, (
        f"Unknown tools in {path}: {unknown_tools}"
    )

    if expected_tools is not None:
        assert normal_tools == expected_tools, (
            f"Unexpected built-in tools in {path}: {normal_tools}"
        )

    return config


def validate_evaluation(path):
    assert path.is_file(), (
        f"Evaluation config not found: {path}"
    )

    config = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    assert isinstance(config, dict), (
        "Invalid evaluation config"
    )

    evaluation = config.get("evaluation")

    assert isinstance(evaluation, dict), (
        "Missing evaluation section"
    )

    required_fields = {
        "timeout_seconds": (1, 3600),
        "max_tool_calls": (1, 1000),
        "max_time_minutes": (1, 1440),
        "max_turns": (1, 10000),
    }

    for field, (minimum, maximum) in required_fields.items():

        value = evaluation.get(field)

        assert type(value) is int, (
            f"{field} must be an integer"
        )

        assert minimum <= value <= maximum, (
            f"{field} must be between {minimum} and {maximum}"
        )

    return evaluation


def validate_delegation(root_config):

    root_tools = root_config.get("tools", [])

    # Code Analyzer must be registered as AgentTool
    agent_tool_paths = {
        tool["agent_tool"]["config_path"]
        for tool in root_tools
        if isinstance(tool, dict)
        and isinstance(tool.get("agent_tool"), dict)
    }

    expected_agent_tools = {
        "sub_agents/code_analyzer.yaml"
    }

    assert agent_tool_paths == expected_agent_tools, (
        f"Invalid AgentTool registrations: {agent_tool_paths}"
    )

    # Tester must be registered through sub_agents
    sub_agents = root_config.get("sub_agents", [])

    assert isinstance(sub_agents, list), (
        "sub_agents must be a list"
    )

    connected_paths = {
        item.get("config_path")
        for item in sub_agents
        if isinstance(item, dict)
    }

    expected_sub_agents = {
        "sub_agents/tester.yaml"
    }

    assert connected_paths == expected_sub_agents, (
        f"Invalid sub-agent connections: {connected_paths}"
    )

    return agent_tool_paths, connected_paths


def main():

    print("=" * 50)
    print("GEMMA AGENT CONFIGURATION VALIDATION")
    print("=" * 50)

    # 1. Root Agent
    root_config = validate_agent(
        ROOT / "agent.yaml"
    )

    # 2. Read-only tool permissions
    read_only_tools = {
        "read_file",
        "search_similar_code",
        "get_code_neighbors",
        "get_code_subgraph",
    }

    # 3. Code Analyzer
    analyzer_config = validate_agent(
        ROOT / "sub_agents" / "code_analyzer.yaml",
        expected_tools=read_only_tools,
    )

    # 4. Testing Agent
    tester_config = validate_agent(
        ROOT / "sub_agents" / "tester.yaml",
        expected_tools=read_only_tools,
    )

    # 5. Model consistency
    models = {
        root_config["model"],
        analyzer_config["model"],
        tester_config["model"],
    }

    assert len(models) == 1, (
        f"Model mismatch found: {models}"
    )

    # 6. Delegation architecture
    agent_tool_paths, connected_paths = (
        validate_delegation(root_config)
    )

    # 7. Evaluation configuration
    evaluation = validate_evaluation(
        ROOT / "eval_config.yaml"
    )

    # 8. Report
    print("\nAgent Configuration")
    print("-" * 30)

    print("Root Agent:", root_config["name"])
    print("Code Analyzer:", analyzer_config["name"])
    print("Testing Agent:", tester_config["name"])

    print("\nModel:", root_config["model"])

    print("\nDelegation Architecture")
    print("-" * 30)

    print("Code Analyzer: AgentTool")
    print("Testing Agent: sub_agents")
    print("AgentTool registrations:", len(agent_tool_paths))
    print("Sub-agent registrations:", len(connected_paths))

    print("\nEvaluation Configuration")
    print("-" * 30)

    for field, value in evaluation.items():
        print(f"{field}: {value}")

    print("\n" + "=" * 50)
    print("ALL LOCAL CONFIGURATION CHECKS PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
