# parsers/rule_preprocess.py
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from config import get_ai_model

# Load environment variables from .env if present
load_dotenv()

model_name = get_ai_model()

# Define the preprocess agent
preprocess_agent = Agent(
    model_name,
    system_prompt=(
        "You are an academic rule preprocessor. Your task is to simplify raw USYD unit requirement text "
        "into a normalized, regular-expression-friendly format.\n\n"
        "Instructions:\n"
        "1. Simplify all mark-specific or average mark constraints to simple completion. "
        "Remove mark thresholds and keep only the unit codes or credit points.\n"
        "2. Strip postgraduate/degree candidate restrictions if they represent the entire requirement, treating them as no requirement.\n"
        "3. Standardize logical operators to simple 'and' / 'or'.\n"
        "4. Standardize credit point expressions (e.g., '12cp' -> '12 credit points').\n"
        "5. If a rule is highly complex (e.g. contains nested lists of credit points, complex conditional logic, or cannot be simplified to a simple regex-solvable rule), output exactly '[CURATE]'. Do not attempt to parse or simplify it.\n"
        "6. Return ONLY the simplified rule text (or '[CURATE]'), with no extra commentary or formatting.\n\n"
        "Formatting Examples:\n"
        "- Input: 'a mark of 65 or above in COMP2123' -> Output: 'COMP2123'\n"
        "- Input: 'average of 65 in 12cp of COMP' -> Output: '12 credit points of COMP'\n"
        "- Input: 'A candidate for MIT who has completed 36 credit points' -> Output: '36 credit points'\n"
        "- Input: 'Completion of 24 credit points of units of study from the Units of Study Table for the Master of Cultural Studies' -> Output: 'None'\n"
        "- Input: '(ANAT2008 and ANAT2011) and 6 credit points from (ANAT3X04 or ANAT3X07 or ANAT3X08 or ANAT3009)' -> Output: '[CURATE]'\n"
        "- Input: 'BBHE1006 or DATA1X01 or 48 credit points of any 1000 or 2000-level units in (ANAT or AVBS or BCMB...)' -> Output: '[CURATE]'"
    )
)

async def parse_rules_with_preprocess(rule_text: str) -> str:
    """
    Asynchronously preprocesses USYD rule text using Preprocess Agent.
    If the API call fails, times out, or errors, returns original text to fall back.
    """
    clean_text = rule_text.strip()
    if not clean_text or clean_text.lower() in ["none", "none."]:
        return "None"
        
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(preprocess_agent.run(clean_text), timeout=15.0)
            return response.output.strip()
        except UnexpectedModelBehavior as umb:
            print(f"Preprocess Agent unexpected model behavior: {umb}")
            return clean_text
        except asyncio.TimeoutError:
            print(f"Preprocess Agent timeout on attempt {attempt+1}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Preprocess Agent exception: {e}")
            return clean_text
            
    return clean_text
