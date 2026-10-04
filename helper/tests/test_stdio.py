"""Real subprocess stdio handshake; no game and no network transport."""
from pathlib import Path
import sys

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


def test_sdk_stdio_registration():
    async def exercise():
        helper = Path(__file__).resolve().parents[1]
        parameters = StdioServerParameters(command=sys.executable,
            args=["-m", "domus_helper.mcp_server"], cwd=str(helper),
            env={"DOMUS_AGENT_NAME": "test"})
        with anyio.fail_after(15):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    assert {tool.name for tool in listing.tools} == {
                        "status", "arm", "start", "stop", "disarm", "prepare", "sit", "sit_trial", "trial",
                        "pause", "release", "verdicts", "telemetry", "lineage",
                        "detected_build", "fingerprints",
                        "atlas_dump", "atlas_progress", "atlas_import", "atlas_query", "cards",
                        "tuned_scan", "bridge_status", "thalamus_status",
                        "calibrate", "calibration_report",
                        "trials", "qualification", "crawl_plan"}
    anyio.run(exercise)
