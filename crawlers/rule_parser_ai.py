# crawlers/rule_parser_ai.py
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from crawlers.rule_schemas import RuleParseResult

# Load environment variables from .env if present
load_dotenv()

# Determine which model to use based on environment keys
gemini_key = os.getenv("GEMINI_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

if gemini_key:
    # Use Gemini model with pydantic-ai google provider
    os.environ["GOOGLE_API_KEY"] = gemini_key
    model_name = "google:gemini-3.1-flash-lite"
elif openai_key:
    # Use OpenAI model
    model_name = "openai:gpt-4o-mini"
else:
    # Fallback to test model if no keys are provided (used for test environment)
    from pydantic_ai.models.test import TestModel
    model_name = TestModel()

# Define the agent with the response structure
agent = Agent(
    model_name,
    output_type=RuleParseResult,
    system_prompt=(
        "You are an expert parser for USYD (University of Sydney) academic unit rules.\n"
        "Your task is to parse raw requirement text (prerequisites, corequisites, or prohibitions) "
        "into a structured logic tree conforming to the RuleParseResult schema.\n\n"
        "Rules:\n"
        "1. If there are no requirements, type must be 'none'.\n"
        "2. If the requirement is a single unit code (e.g. COMP2123), output a UnitRequirement.\n"
        "3. If the requirement is a credit point minimum, output a CreditPointRequirement. "
        "For example, '12cp of 3000-level COMP' means:\n"
        "   - credit_points: 12\n"
        "   - level: 3000\n"
        "   - subject: 'COMP'\n"
        "   If the text specifies credit points without a level constraint (e.g. '12cp in MATH'), level should be null.\n"
        "   If it specifies credit points without a subject constraint (e.g. '24cp of units'), subject should be 'ANY'.\n"
        "4. If there are logical combinations (AND / OR), output a LogicalRequirement with nested operands. "
        "Ensure complex nested rules are nested properly (e.g., '(A or B) and C' becomes an AND node with "
        "operands: [OR node with operands [A, B], C].\n"
        "5. If a rule specifies assumed knowledge or general text that cannot fit other requirements, "
        "you should still attempt to parse it structurally or default to 'none' if it contains no strict prerequisites.\n"
        "Be extremely precise. Match unit codes (4 letters, 4 digits) exactly."
    )
)

async def parse_rules_with_ai(rule_text: str) -> RuleParseResult:
    """
    Asynchronously parses USYD rule text into a RuleParseResult using Pydantic AI agent.
    If the API call fails, times out, or fails to validate, returns a RuleParseResult with type="none".
    """
    clean_text = rule_text.strip()
    if not clean_text or clean_text.lower() in ["none", "none."]:
        return RuleParseResult(type="none", rule=None)
        
    for attempt in range(3):
        try:
            # Wrap in a 60-second timeout to accommodate model reasoning/thinking latency
            response = await asyncio.wait_for(agent.run(clean_text), timeout=60.0)
            return response.output
        except asyncio.TimeoutError:
            print(f"[{clean_text[:15]}...] AI parsing timed out after 60.0 seconds.")
            return RuleParseResult(type="none", rule=None)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                sleep_time = 12.0 + attempt * 5.0
                print(f"[{clean_text[:15]}...] Rate limit (429) hit. Retrying in {sleep_time} seconds (attempt {attempt + 1}/3)...")
                await asyncio.sleep(sleep_time)
                continue
            print(f"Error parsing rule text with AI fallback: '{rule_text}'. Error: {e}")
            return RuleParseResult(type="none", rule=None)
            
    print(f"[{clean_text[:15]}...] All AI parsing attempts failed due to rate limits.")
    return RuleParseResult(type="none", rule=None)

if __name__ == "__main__":
    # Test harness
    async def main():
        test_cases = [
            "None",
            "COMP2123",
            "(COMP2123 or COMP2823) and 12cp of 3000-level COMP"
        ]
        for case in test_cases:
            res = await parse_rules_with_ai(case)
            print(f"Text: '{case}' -> Parsed: {res.model_dump_json(indent=2)}")

    asyncio.run(main())
