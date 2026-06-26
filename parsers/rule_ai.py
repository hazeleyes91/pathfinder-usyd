# parsers/rule_ai.py
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from parsers.schemas import RuleParseResult
from config import get_ai_model

# Load environment variables from .env if present
load_dotenv()

model_name = get_ai_model()

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
        "2. If the requirement is a single unit code (e.g. COMP2123, DATA1X01), output a UnitRequirement.\n"
        "3. If the requirement is a credit point minimum, output a CreditPointRequirement. "
        "For example, '12cp of 3000-level COMP' means:\n"
        "   - credit_points: 12\n"
        "   - level: 3000\n"
        "   - subjects: ['COMP']\n"
        "   If the text specifies credit points without a level constraint (e.g. '12cp in MATH'), level should be null.\n"
        "   If it specifies credit points without a subject constraint (e.g. '24cp of units'), both unit_codes and subjects should be null.\n"
        "   If it specifies 'from (UNIT1 or UNIT2 or ...)', populate unit_codes with those codes; subjects should be null.\n"
        "   If it specifies a set of subject prefixes (e.g. '48cp of [ANAT or BIOL]'), populate subjects with those prefixes; unit_codes should be null.\n"
        "4. If there are logical combinations (AND / OR), output a LogicalRequirement with nested operands. "
        "Ensure complex nested rules are nested properly (e.g., '(A or B) and C' becomes an AND node with "
        "operands: [OR node with operands [A, B], C].\n"
        "5. If a rule specifies assumed knowledge or general text that cannot fit other requirements, "
        "you should still attempt to parse it structurally or default to 'none' if it contains no strict prerequisites.\n"
        "6. Treat all mark-specific or average mark requirements as completion tasks: ignore the mark threshold/constraint "
        "and parse only the underlying unit or credit point requirement (e.g. parse 'a mark of 65 or above in COMP2123' "
        "simply as a UnitRequirement for 'COMP2123', and 'average of 65 in 12cp of COMP' as a CreditPointRequirement "
        "for 12 credit points of COMP).\n"
        "7. Treat all postgraduate or degree-specific candidate/admission rules (e.g. 'A candidate for MIT...', "
        "'Completion of 24 credit points... for the Master of Cultural Studies') as no requirement: output type 'none' with rule null.\n"
        "Be extremely precise. Match unit codes (4 letters followed by 4 digits or 'X' wildcards, e.g. COMP2X21, BIOL2XXX) exactly."
    )
)

async def parse_rules_with_ai(rule_text: str) -> RuleParseResult:
    """
    Parses requirement text using LLM fallback agent.
    Performs up to 3 retry attempts under API exceptions.
    Returns RuleParseResult.
    """
    clean_text = rule_text.strip()
    if not clean_text or clean_text.lower() in ["none", "none."]:
        return RuleParseResult(type="none", rule=None)
        
    for attempt in range(3):
        try:
            # Wrap in a 90-second timeout to accommodate model reasoning/thinking latency
            response = await asyncio.wait_for(agent.run(clean_text), timeout=90.0)
            return response.output
        except asyncio.TimeoutError:
            print(f"[{clean_text[:15]}...] AI parsing timed out after 90.0 seconds.")
            return RuleParseResult(type="none", rule=None)
        except UnexpectedModelBehavior as e:
            # Covers "model output must contain either output text or tool calls" and similar
            # empty or malformed model responses. Retry with brief backoff.
            sleep_time = 5.0 * (attempt + 1)
            print(f"[{clean_text[:15]}...] Unexpected model behavior (attempt {attempt + 1}/3): {e}. Retrying in {sleep_time:.0f}s...")
            await asyncio.sleep(sleep_time)
            continue
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Exponential backoff: 15s, 30s, 60s to respect free-tier burst limits
                sleep_time = 15.0 * (2 ** attempt)
                print(f"[{clean_text[:15]}...] Rate limit (429) hit. Retrying in {sleep_time:.0f}s (attempt {attempt + 1}/3)...")
                await asyncio.sleep(sleep_time)
                continue
            print(f"Error parsing rule text with AI fallback: '{rule_text}'. Error: {e}")
            return RuleParseResult(type="none", rule=None)
            
    print(f"[{clean_text[:15]}...] All AI parsing attempts failed. Tagging for curation.")
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
