# tests/test_rule_parser.py
import unittest
from unittest.mock import patch, AsyncMock
import asyncio
from parsers.rule_regex import parse_rules_with_regex
from parsers.rule_ai import parse_rules_with_ai
from parsers.schemas import RuleParseResult, UnitRequirement

class TestRuleParsers(unittest.TestCase):
    
    def test_regex_none(self):
        result = parse_rules_with_regex("None")
        self.assertEqual(result, {"type": "none"})
        
    def test_regex_single_unit(self):
        result = parse_rules_with_regex("COMP2123")
        self.assertEqual(result, {"type": "unit", "unit_code": "COMP2123"})
        
    def test_regex_or_chain(self):
        result = parse_rules_with_regex("INFO1110 or INFO1910")
        self.assertEqual(result["type"], "unit_group")
        self.assertEqual(result["operator"], "OR")
        self.assertEqual(set(result["unit_codes"]), {"INFO1110", "INFO1910"})
        
    def test_regex_complex_fallback(self):
        # Should return None for complex rules, triggering the AI fallback
        result = parse_rules_with_regex("(COMP2123 or COMP2823) and 12cp of 3000-level COMP")
        self.assertIsNone(result)

    def test_regex_simple_credit_points(self):
        # Should parse simple total credit point requirements
        result1 = parse_rules_with_regex("96 credit points")
        self.assertEqual(result1, {
            "type": "credit_points",
            "credit_points": 96,
            "level": None,
            "unit_codes": None,
            "subjects": None
        })
        result2 = parse_rules_with_regex("A minimum of 72 credit points")
        self.assertEqual(result2, {
            "type": "credit_points",
            "credit_points": 72,
            "level": None,
            "unit_codes": None,
            "subjects": None
        })
        result3 = parse_rules_with_regex("Completion of 72 credit points of units of study")
        self.assertEqual(result3, {
            "type": "credit_points",
            "credit_points": 72,
            "level": None,
            "unit_codes": None,
            "subjects": None
        })

    def test_regex_postgrad_ignored(self):
        # Should ignore postgraduate/degree candidate rules and return type='none'
        result1 = parse_rules_with_regex("A candidate for MIT who has completed 36 credit points")
        self.assertEqual(result1, {"type": "none"})
        result2 = parse_rules_with_regex("Completion of 24 credit points of units of study from the Units of Study Table for the Master of Cultural Studies")
        self.assertEqual(result2, {"type": "none"})

    def test_regex_wildcards(self):
        # Test single code with wildcards
        self.assertEqual(parse_rules_with_regex("DATA1X01"), {"type": "unit", "unit_code": "DATA1X01"})
        self.assertEqual(parse_rules_with_regex("BIOL2XXX"), {"type": "unit", "unit_code": "BIOL2XXX"})
        # Test OR sequence with wildcards
        result_or = parse_rules_with_regex("AVBS100X or BIOL1XXX")
        self.assertEqual(result_or["type"], "unit_group")
        self.assertEqual(result_or["operator"], "OR")
        self.assertEqual(set(result_or["unit_codes"]), {"AVBS100X", "BIOL1XXX"})
        # Test AND sequence with wildcards
        result_and = parse_rules_with_regex("GEOS2X14 and GEOS2X24")
        self.assertEqual(result_and["type"], "unit_group")
        self.assertEqual(result_and["operator"], "AND")
        self.assertEqual(set(result_and["unit_codes"]), {"GEOS2X14", "GEOS2X24"})

    def test_ai_fallback_called(self):
        # Run async test inside synchronous test runner using asyncio
        async def run_test():
            with patch('parsers.rule_ai.agent.run', new_callable=AsyncMock) as mock_agent_run:
                mock_response = AsyncMock()
                mock_response.output = RuleParseResult(
                    type="unit",
                    rule=UnitRequirement(type="unit", unit_code="COMP2123")
                )
                mock_agent_run.return_value = mock_response
                
                result = await parse_rules_with_ai("COMP2123")
                self.assertEqual(result.type, "unit")
                self.assertEqual(result.rule.unit_code, "COMP2123")
                mock_agent_run.assert_called_once_with("COMP2123")
                
        asyncio.run(run_test())

    def test_preprocess_agent_called(self):
        # Async test inside sync runner
        async def run_test():
            from parsers.rule_preprocess import parse_rules_with_preprocess
            with patch('parsers.rule_preprocess.preprocess_agent.run', new_callable=AsyncMock) as mock_run:
                mock_response = AsyncMock()
                mock_response.output = "COMP2123"
                mock_run.return_value = mock_response
                
                res = await parse_rules_with_preprocess("a mark of 65 or above in COMP2123")
                self.assertEqual(res, "COMP2123")
                mock_run.assert_called_once_with("a mark of 65 or above in COMP2123")
        asyncio.run(run_test())

    def test_preprocess_curate_discard(self):
        # Test that [CURATE] causes the pipeline to skip AI Expert and request curation immediately
        async def run_test():
            from parsers.rules import parse_rule_field
            with patch('parsers.rules.parse_rules_with_preprocess', new_callable=AsyncMock) as mock_preprocess, \
                 patch('parsers.rules.parse_rules_with_ai', new_callable=AsyncMock) as mock_ai:
                 
                mock_preprocess.return_value = "[CURATE]"
                
                parsed_expr, needs_curation = await parse_rule_field(
                    "some complex rule text", "Prerequisites", "COMP3888", has_keys=True
                )
                self.assertEqual(parsed_expr["type"], "none")
                self.assertIsNone(parsed_expr["rule"])
                self.assertTrue(needs_curation)
                mock_preprocess.assert_called_once_with("some complex rule text")
                mock_ai.assert_not_called()
        asyncio.run(run_test())

    def test_detect_soft_warnings(self):
        from parsers.rules import wrap_and_detect_warnings
        from parsers.schemas import ParserWarning
        
        # Postgrad warning
        res1 = wrap_and_detect_warnings("A candidate for MIT who has completed 36 credit points", {"type": "none"}, needs_curation=True)
        self.assertIn(ParserWarning.DEGREE_RESTRICTION, res1.get("warnings"))
        
        # Mark threshold warning
        res2 = wrap_and_detect_warnings("a mark of 65 or above in COMP2123", {"type": "unit", "unit_code": "COMP2123"}, needs_curation=False)
        self.assertIn(ParserWarning.GRADE_THRESHOLD, res2.get("warnings"))
        
        # No warning for standard rules
        res3 = wrap_and_detect_warnings("COMP2123", {"type": "unit", "unit_code": "COMP2123"}, needs_curation=False)
        self.assertIsNone(res3.get("warnings"))

    def test_unit_lifecycle_status(self):
        from parsers.base import parse_unit_html
        import tempfile
        from pathlib import Path
        
        # Test 1: Discontinued placeholder marker file
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "COMP9999.html"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write('<html><body><div id="status">DISCONTINUED</div></body></html>')
            
            res = parse_unit_html(filepath)
            self.assertEqual(res["unit_code"], "COMP9999")
            self.assertEqual(res["status"], "INACTIVE")
            self.assertIsNone(res["resolved_year"])
            
        # Test 2: Explicit discontinued text in HTML
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "COMP9998.html"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write('<html><body>This unit of study is discontinued.</body></html>')
            
            res = parse_unit_html(filepath)
            self.assertEqual(res["status"], "INACTIVE")
            
        # Test 3: Normal active unit with resolved year
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "COMP2123.html"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write('<html><body><h1>COMP2123</h1><p>2026 unit information</p><table><tr><th>Credit points</th><td>6</td></tr></table></body></html>')
            
            res = parse_unit_html(filepath)
            self.assertEqual(res["status"], "ACTIVE")
            self.assertEqual(res["resolved_year"], 2026)

    def test_regex_nested_logical(self):
        # Allow nested deep matching up to 2 levels (e.g. nested AND/OR)
        result1 = parse_rules_with_regex("(INFO1110 or INFO1910) and (MATH1021 or MATH1921)")
        self.assertEqual(result1["type"], "logical")
        self.assertEqual(result1["operator"], "AND")
        self.assertEqual(len(result1["operands"]), 2)
        
        op1 = result1["operands"][0]
        self.assertEqual(op1["type"], "unit_group")
        self.assertEqual(op1["operator"], "OR")
        self.assertEqual(set(op1["unit_codes"]), {"INFO1110", "INFO1910"})
        
        op2 = result1["operands"][1]
        self.assertEqual(op2["type"], "unit_group")
        self.assertEqual(op2["operator"], "OR")
        self.assertEqual(set(op2["unit_codes"]), {"MATH1021", "MATH1921"})
        
        result2 = parse_rules_with_regex("COMP2123 or (INFO1110 and INFO1113)")
        self.assertEqual(result2["type"], "logical")
        self.assertEqual(result2["operator"], "OR")
        self.assertEqual(result2["operands"][0], {"type": "unit", "unit_code": "COMP2123"})
        
        op2_2 = result2["operands"][1]
        self.assertEqual(op2_2["type"], "unit_group")
        self.assertEqual(op2_2["operator"], "AND")
        self.assertEqual(set(op2_2["unit_codes"]), {"INFO1110", "INFO1113"})

    def test_regex_selection_lists(self):
        # Specific selection lists
        res1 = parse_rules_with_regex("12 credit points from (AGRO3004 or AGRI2001 or BIOL2X31 or AGEN2005)")
        self.assertEqual(res1["type"], "credit_points")
        self.assertEqual(res1["credit_points"], 12)
        self.assertEqual(set(res1["unit_codes"]), {"AGRO3004", "AGRI2001", "BIOL2X31", "AGEN2005"})
        self.assertIsNone(res1["level"])
        self.assertIsNone(res1["subjects"])

        # Subject prefix and level
        res2 = parse_rules_with_regex("12 credit points of HPSC2XXX")
        self.assertEqual(res2["type"], "credit_points")
        self.assertEqual(res2["credit_points"], 12)
        self.assertEqual(res2["level"], 2)
        self.assertEqual(res2["subjects"], ["HPSC"])
        self.assertIsNone(res2["unit_codes"])

        # Level specific subject list
        res3 = parse_rules_with_regex("48 credit points of any 1000 or 2000-level units in (ANAT or AVBS or CHEM)")
        self.assertEqual(res3["type"], "credit_points")
        self.assertEqual(res3["credit_points"], 48)
        self.assertEqual(set(res3["subjects"]), {"ANAT", "AVBS", "CHEM"})
        self.assertIsNone(res3["unit_codes"])

    def test_regex_compound_selection_lists(self):
        # ANAT3888 prerequisites
        res = parse_rules_with_regex("(ANAT2008 and ANAT2011) and 6 credit points from (ANAT3X04 or ANAT3X07 or ANAT3X08 or ANAT3009)")
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "logical")
        self.assertEqual(res["operator"], "AND")
        self.assertEqual(len(res["operands"]), 2)
        
        # Check first operand: UnitGroup (ANAT2008 and ANAT2011)
        op1 = res["operands"][0]
        self.assertEqual(op1["type"], "unit_group")
        self.assertEqual(op1["operator"], "AND")
        self.assertEqual(set(op1["unit_codes"]), {"ANAT2008", "ANAT2011"})
        
        # Check second operand: CreditPoint selection (6 credit points from ...)
        op2 = res["operands"][1]
        self.assertEqual(op2["type"], "credit_points")
        self.assertEqual(op2["credit_points"], 6)
        self.assertEqual(set(op2["unit_codes"]), {"ANAT3X04", "ANAT3X07", "ANAT3X08", "ANAT3009"})

        # BCMB3888 prerequisites (excluding simple CP total for simplicity)
        res2 = parse_rules_with_regex("6 credit points from [BCMB2X01 or MEDS2003] and 6 credit points from BCMB2X02")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["type"], "logical")
        self.assertEqual(res2["operator"], "AND")
        self.assertEqual(res2["operands"][0]["type"], "credit_points")
        self.assertEqual(res2["operands"][0]["credit_points"], 6)
        self.assertEqual(set(res2["operands"][0]["unit_codes"]), {"BCMB2X01", "MEDS2003"})
        self.assertEqual(res2["operands"][1]["type"], "credit_points")
        self.assertEqual(res2["operands"][1]["credit_points"], 6)
        # Note: BCMB2X02 is parsed as a unit requirement within CP_SELECTION or direct
        self.assertEqual(set(res2["operands"][1]["unit_codes"]), {"BCMB2X02"})

if __name__ == '__main__':
    unittest.main()
