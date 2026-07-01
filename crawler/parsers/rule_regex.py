# parsers/rule_regex.py
import re

def tokenize(text: str):
    token_re = re.compile(
        r'(?P<CP_SELECTION>\b\d+\s*(?:credit\s*points|cp|p)\s+(?:from|of|including)\s+[\(\[](?:[A-Z]{4}[0-9X]{4}\b|or|and|\s|,|[\(\)\[\]])+[\)\]]|\b\d+\s*(?:credit\s*points|cp|p)\s+(?:from|including)\s+[A-Z]{4}[0-9X]{4}\b)|'
        r'(?P<CP_MULTI_SUBJECT>\b\d+\s*(?:credit\s*points|cp|p)\s+(?:of|at)\s+(?:any\s+)?(?:\d+[\s-]*(?:or\s+\d+)?[\s-]*(?:level)\s+(?:units\s+)?in\s+)?[\(\[](?:[A-Z]{4}\b|or|and|\s|,|[\(\)\[\]])+[\)\]])|'
        r'(?P<CP_SUBJECT_LEVEL>\b\d+\s*(?:credit\s*points|cp|p)\s+of\s+[A-Z]{4}[0-9X]*)|'
        r'(?P<CP_TOTAL>\b\d+\s*(?:credit\s*points|cp)\b)|'
        r'(?P<LPAREN>\()|'
        r'(?P<RPAREN>\))|'
        r'(?P<OPERATOR>\b(?:and|or)\b)|'
        r'(?P<UNIT>\b[A-Z]{4}[0-9X]{4}\b)|'
        r'(?P<WS>\s+)|'
        r'(?P<MISC>\S+)',
        re.IGNORECASE
    )
    tokens = []
    for mo in token_re.finditer(text):
        kind = mo.lastgroup
        value = mo.group(kind)
        if kind == 'WS':
            continue
        elif kind == 'MISC':
            return None
        tokens.append((kind, value))
    return tokens

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_kind=None):
        tok = self.peek()
        if not tok:
            raise SyntaxError("Unexpected end of input")
        if expected_kind and tok[0] != expected_kind:
            raise SyntaxError(f"Expected {expected_kind}, got {tok[0]}")
        self.pos += 1
        return tok

    def parse(self):
        result = self.expr()
        if self.peek() is not None:
            raise SyntaxError("Unexpected trailing tokens")
        return result

    def expr(self):
        node = self.term()
        while True:
            tok = self.peek()
            if tok and tok[0] == 'OPERATOR' and tok[1].lower() == 'or':
                self.consume()
                right = self.term()
                if node.get("type") == "logical" and node.get("operator") == "OR":
                    node["operands"].append(right)
                else:
                    node = {
                        "type": "logical",
                        "operator": "OR",
                        "operands": [node, right]
                    }
            else:
                break
        return node

    def term(self):
        node = self.factor()
        while True:
            tok = self.peek()
            if tok and tok[0] == 'OPERATOR' and tok[1].lower() == 'and':
                self.consume()
                right = self.factor()
                if node.get("type") == "logical" and node.get("operator") == "AND":
                    node["operands"].append(right)
                else:
                    node = {
                        "type": "logical",
                        "operator": "AND",
                        "operands": [node, right]
                    }
            else:
                break
        return node

    def factor(self):
        tok = self.peek()
        if not tok:
            raise SyntaxError("Unexpected end of input in factor")
        
        if tok[0] == 'UNIT':
            self.consume()
            return {
                "type": "unit",
                "unit_code": tok[1].upper()
            }
        elif tok[0] == 'LPAREN':
            self.consume()
            node = self.expr()
            self.consume('RPAREN')
            return node
        elif tok[0] == 'CP_SELECTION':
            self.consume()
            text = tok[1]
            match = re.match(
                r"^(\d+)\s*(?:credit\s*points|cp|p)\s+(?:from|of|including)\s+(?:[\(\[](.*?)[\)\]]|([A-Z]{4}[0-9X]{4}))$",
                text,
                re.IGNORECASE
            )
            if not match:
                raise SyntaxError(f"Invalid CP_SELECTION format: {text}")
            cps = int(match.group(1))
            if cps % 6 != 0:
                raise SyntaxError(f"Credit points {cps} is not a multiple of 6")
            inner_text = match.group(2) or match.group(3)
            units = re.findall(r"\b[A-Z]{4}[0-9X]{4}\b", inner_text, re.IGNORECASE)
            return {
                "type": "credit_points",
                "credit_points": cps,
                "level": None,
                "unit_codes": list(set(u.upper() for u in units)),
                "subjects": None
            }
        elif tok[0] == 'CP_MULTI_SUBJECT':
            self.consume()
            text = tok[1]
            match = re.match(
                r"^(\d+)\s*(?:credit\s*points|cp|p)\s+(?:of|at)\s+(?:any\s+)?(?:(\d+)[\s-]*(?:or\s+\d+)?[\s-]*(?:level)\s+(?:units\s+)?in\s+)?[\(\[](.*?)[\)\]]$",
                text,
                re.IGNORECASE
            )
            if not match:
                raise SyntaxError(f"Invalid CP_MULTI_SUBJECT format: {text}")
            cps = int(match.group(1))
            if cps % 6 != 0:
                raise SyntaxError(f"Credit points {cps} is not a multiple of 6")
            inner_text = match.group(3)
            subjects = re.findall(r"\b[A-Z]{4}\b", inner_text, re.IGNORECASE)
            return {
                "type": "credit_points",
                "credit_points": cps,
                "level": None,
                "unit_codes": None,
                "subjects": list(set(s.upper() for s in subjects))
            }
        elif tok[0] == 'CP_SUBJECT_LEVEL':
            self.consume()
            text = tok[1]
            match = re.match(
                r"^(\d+)\s*(?:credit\s*points|cp|p)\s+of\s+([A-Z]{4})(\d)?[X0-9]*$",
                text,
                re.IGNORECASE
            )
            if not match:
                raise SyntaxError(f"Invalid CP_SUBJECT_LEVEL format: {text}")
            cps = int(match.group(1))
            if cps % 6 != 0:
                raise SyntaxError(f"Credit points {cps} is not a multiple of 6")
            subject = match.group(2).upper()
            level_str = match.group(3)
            level = int(level_str) if level_str else None
            return {
                "type": "credit_points",
                "credit_points": cps,
                "level": level,
                "unit_codes": None,
                "subjects": [subject]
            }
        elif tok[0] == 'CP_TOTAL':
            self.consume()
            text = tok[1]
            match = re.match(
                r"^(\d+)\s*(?:credit\s*points|cp)\b",
                text,
                re.IGNORECASE
            )
            if not match:
                raise SyntaxError(f"Invalid CP_TOTAL format: {text}")
            cps = int(match.group(1))
            if cps % 6 != 0:
                raise SyntaxError(f"Credit points {cps} is not a multiple of 6")
            return {
                "type": "credit_points",
                "credit_points": cps,
                "level": None,
                "unit_codes": None,
                "subjects": None
            }
        else:
            raise SyntaxError(f"Unexpected token in factor: {tok}")

def simplify_ast(node: dict) -> dict:
    if not node:
        return node
        
    if node.get("type") == "logical":
        # 1. Recursively simplify operands
        node["operands"] = [simplify_ast(op) for op in node["operands"]]
        
        # 2. Partition operands into unit codes and other requirements
        unit_codes = set()
        other_operands = []
        
        for op in node["operands"]:
            if op.get("type") == "unit":
                unit_codes.add(op["unit_code"])
            elif op.get("type") == "unit_group" and op.get("operator") == node["operator"]:
                unit_codes.update(op["unit_codes"])
            else:
                other_operands.append(op)
                
        # 3. Rebuild operands list
        if len(unit_codes) > 0:
            if len(unit_codes) == 1 and len(other_operands) == 0:
                return {
                    "type": "unit",
                    "unit_code": list(unit_codes)[0]
                }
            elif len(unit_codes) >= 2:
                ug = {
                    "type": "unit_group",
                    "operator": node["operator"],
                    "unit_codes": list(unit_codes)
                }
                if len(other_operands) == 0:
                    return ug
                node["operands"] = [ug] + other_operands
            else:
                u = {
                    "type": "unit",
                    "unit_code": list(unit_codes)[0]
                }
                node["operands"] = [u] + other_operands
                
        # 4. If only one operand remains, return it directly
        if len(node["operands"]) == 1:
            return node["operands"][0]
            
    return node

def parse_rules_with_regex(rule_text: str) -> dict | None:
    """
    Tries to parse raw prerequisite text into structured logic using Regex/Parser.
    Returns a dictionary if successfully parsed, or None if too complex (requires AI).
    """
    clean_text = rule_text.strip().rstrip(".")
    
    # 0. Clean equivalent study variations and normalize brackets
    clean_text = re.sub(r"\s+or\s+equivalent\s+study\s+at\s+another\s+institution", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\s+or\s+equivalent\s+unit\s+of\s+study", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\s+or\s+equivalent", "", clean_text, flags=re.IGNORECASE)
    clean_text = clean_text.replace("{", "(").replace("}", ")").replace("[", "(").replace("]", ")")
    
    # Remove common prefixes/suffixes for credit points/units of study
    clean_text = re.sub(r"^(?:a\s+minimum\s+of\s+|completion\s+of\s+|minimum\s+of\s+)", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"^(?:a\s+mark\s+of\s+\d+\s*(?:or\s+above)?\s+in\s+|an\s+average\s+mark\s+of\s+\d+\s+in\s+|average\s+of\s+\d+\s+in\s+)", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"(?:\s+of\s+units\s+of\s+study|\s+of\s+units)$", "", clean_text, flags=re.IGNORECASE)
    
    # 1. Check for "None"
    if clean_text.lower() in ["none", "none.", "none (including advanced versions)", ""]:
        return {"type": "none"}
        
    # 2. Check for postgraduate or degree-specific candidate rules (ignored/treated as no rule)
    if re.search(r"candidate\s+for|Master\s+of|enrolled\s+in", clean_text, re.IGNORECASE):
        return {"type": "none"}
        
    # 3. Try parsing as a nested logical expression of units and selection lists
    tokens = tokenize(clean_text)
    if tokens is None:
        return None
        
    try:
        parser = Parser(tokens)
        parsed_ast = parser.parse()
        return simplify_ast(parsed_ast)
    except SyntaxError:
        return None

if __name__ == "__main__":
    # Sample Test run
    test_cases = [
        "None",
        "COMP2123",
        "INFO1110 or INFO1910 or INFO1113",
        "COMP2123 and MATH1064",
        "(INFO1110 or INFO1910) and (MATH1021 or MATH1921)",
        "(COMP2123 or COMP2823) and 12cp of 3000-level COMP"
    ]
    for case in test_cases:
        res = parse_rules_with_regex(case)
        print(f"Text: '{case}' -> Result: {res}")
