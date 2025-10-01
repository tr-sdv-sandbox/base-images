"""
Expression evaluator for complex conditions in test expectations.
Supports comparison operators, logical operators, and simple arithmetic.
"""

import ast
import operator
from typing import Any, Dict, Optional, Union


class ExpressionEvaluator:
    """
    Safe expression evaluator for test conditions.
    
    Supports:
    - Comparison: ==, !=, <, <=, >, >=
    - Logical: and, or, not
    - Arithmetic: +, -, *, /, %
    - Membership: in, not in
    - Variables: referenced as names (e.g., x, temperature)
    - Constants: numbers, strings, booleans
    
    Examples:
    - "x > 100"
    - "temperature >= 20 and temperature <= 30"
    - "state == 'IDLE' or state == 'OFF'"
    - "value in [1, 2, 3]"
    - "not error_flag"
    """
    
    # Allowed AST node types for safety
    ALLOWED_NODES = {
        ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp,
        ast.Name, ast.Constant, ast.Num, ast.Str,
        ast.List, ast.Tuple, ast.Set,
        ast.Load, ast.And, ast.Or, ast.Not,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.In, ast.NotIn,
        ast.NameConstant,  # For True/False/None in older Python
    }
    
    # Operator mappings
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda x, y: x and y,
        ast.Or: lambda x, y: x or y,
        ast.Not: operator.not_,
        ast.In: lambda x, y: x in y,
        ast.NotIn: lambda x, y: x not in y,
    }
    
    def __init__(self):
        self._cache: Dict[str, ast.AST] = {}
    
    def evaluate(self, expression: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Evaluate an expression with optional variable context.
        
        Args:
            expression: String expression to evaluate
            context: Dictionary of variable names to values
            
        Returns:
            Result of expression evaluation
            
        Raises:
            ValueError: If expression is invalid or unsafe
            KeyError: If variable is not found in context
        """
        if context is None:
            context = {}
            
        # Parse expression (with caching)
        if expression not in self._cache:
            try:
                tree = ast.parse(expression, mode='eval')
                self._validate_ast(tree)
                self._cache[expression] = tree
            except SyntaxError as e:
                raise ValueError(f"Invalid expression syntax: {e}")
        else:
            tree = self._cache[expression]
        
        # Evaluate
        return self._eval_node(tree.body, context)
    
    def _validate_ast(self, node: ast.AST):
        """Recursively validate AST nodes for safety"""
        for child in ast.walk(node):
            if type(child) not in self.ALLOWED_NODES:
                raise ValueError(f"Unsafe expression: {type(child).__name__} not allowed")
    
    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        """Recursively evaluate AST node"""
        
        # Constants
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Num, ast.Str)):  # For older Python
            return node.n if isinstance(node, ast.Num) else node.s
        elif isinstance(node, ast.NameConstant):  # For older Python
            return node.value
            
        # Variables
        elif isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            else:
                raise KeyError(f"Variable '{node.id}' not found in context")
                
        # Collections
        elif isinstance(node, ast.List):
            return [self._eval_node(elem, context) for elem in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elem, context) for elem in node.elts)
        elif isinstance(node, ast.Set):
            return {self._eval_node(elem, context) for elem in node.elts}
            
        # Comparison operations
        elif isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, context)
                if not self.OPERATORS[type(op)](left, right):
                    return False
                left = right
            return True
            
        # Boolean operations
        elif isinstance(node, ast.BoolOp):
            op_func = self.OPERATORS[type(node.op)]
            values = [self._eval_node(v, context) for v in node.values]
            
            if isinstance(node.op, ast.And):
                result = True
                for v in values:
                    result = op_func(result, v)
                    if not result:
                        break
                return result
            else:  # Or
                result = False
                for v in values:
                    result = op_func(result, v)
                    if result:
                        break
                return result
                
        # Unary operations
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            return self.OPERATORS[type(node.op)](operand)
            
        # Binary operations
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            return self.OPERATORS[type(node.op)](left, right)
            
        else:
            raise ValueError(f"Unsupported node type: {type(node).__name__}")


def parse_expect_value(value: Union[str, Any]) -> tuple[bool, Any]:
    """
    Parse an expectation value, determining if it's an expression.
    
    Returns:
        (is_expression, parsed_value)
    """
    if not isinstance(value, str):
        return False, value
        
    # Check if it looks like an expression
    expression_indicators = ['<', '>', '==', '!=', '>=', '<=', ' and ', ' or ', ' not ', ' in ']
    
    if any(indicator in value for indicator in expression_indicators):
        return True, value
    
    # Try to parse as literal
    try:
        # Try as number
        if '.' in value:
            return False, float(value)
        else:
            return False, int(value)
    except ValueError:
        pass
        
    # Boolean literals
    if value.lower() == 'true':
        return False, True
    elif value.lower() == 'false':
        return False, False
    elif value.lower() == 'none' or value.lower() == 'null':
        return False, None
        
    # String literal
    return False, value


def evaluate_condition(condition: str, actual_value: Any, 
                      expected_value: Any = None) -> tuple[bool, str]:
    """
    Evaluate a test condition.
    
    Args:
        condition: Condition expression (e.g., "> 100", "== 'IDLE'")
        actual_value: Actual value from system
        expected_value: Optional expected value for simple comparisons
        
    Returns:
        (result, description)
    """
    evaluator = ExpressionEvaluator()
    
    # If condition is a simple value, do equality check
    is_expr, parsed = parse_expect_value(condition)
    
    if not is_expr:
        result = actual_value == parsed
        desc = f"Expected {parsed}, got {actual_value}"
        return result, desc
    
    # Evaluate as expression
    try:
        # Build context with common variable names
        context = {
            'value': actual_value,
            'actual': actual_value,
            'x': actual_value,  # Common shorthand
        }
        
        # Add expected value if provided
        if expected_value is not None:
            context['expected'] = expected_value
            
        result = evaluator.evaluate(condition, context)
        desc = f"Condition '{condition}' with value={actual_value}"
        return bool(result), desc
        
    except Exception as e:
        return False, f"Failed to evaluate '{condition}': {e}"