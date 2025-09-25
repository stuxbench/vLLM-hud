"""
Test grader for verifying the grading system works.
checks if TestField was added to the vLLM MODULE_ATTRS dictionary.
"""

import ast
import os

from .spec import EnvironmentState, Grade, SubGrade, Grader


class TestFieldGrader(Grader):
    """
    test grader to check if 'TestField' was added to MODULE_ATTRS in vLLM
    __init__.py.
    """
    name = "TestFieldGrader"
    
    @classmethod
    def compute_score(
        cls,
        state: EnvironmentState,
        working_dir: str = "/workspace/vllm"
    ) -> tuple[float, dict]:
        """
        Check if 'TestField': '.test_field:test_value' was added to
        MODULE_ATTRS in __init__.py.
        
        Returns:
            score 1.0 if field exists with correct value
            score 0.5 if field exists with wrong value  
            score 0.0 if field doesn't exist
        """
        metadata = {}
        
        try:
            init_file_path = os.path.join(working_dir, "vllm", "__init__.py")
            
            if not os.path.exists(init_file_path):
                metadata["error"] = f"File not found: {init_file_path}"
                return (0.0, metadata)
            
            # Read the __init__.py file
            with open(init_file_path, 'r') as f:
                file_content = f.read()
            
            # Parse the file to extract MODULE_ATTRS
            try:
                tree = ast.parse(file_content)
                
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Assign) and
                        len(node.targets) == 1 and
                        isinstance(node.targets[0], ast.Name) and
                        node.targets[0].id == 'MODULE_ATTRS' and
                        isinstance(node.value, ast.Dict)):
                        # Extract dictionary keys and values
                        keys = []
                        values = []
                        
                        for key, value in zip(node.value.keys, 
                                              node.value.values):
                            if isinstance(key, ast.Constant):
                                keys.append(key.value)
                            if isinstance(value, ast.Constant):
                                values.append(value.value)
                        
                        module_attrs_dict = dict(zip(keys, values))
                        metadata["module_attrs_keys"] = (
                            list(module_attrs_dict.keys())[:10]
                        )
                        
                        # Check if TestField exists
                        if "TestField" in module_attrs_dict:
                            actual_value = module_attrs_dict["TestField"]
                            expected_value = ".test_field:test_value"
                            
                            if actual_value == expected_value:
                                metadata["test_field_found"] = True
                                metadata["test_field_value"] = actual_value
                                metadata["result"] = (
                                    "SUCCESS: TestField added with correct "
                                    "value"
                                )
                                return (1.0, metadata)
                            else:
                                metadata["test_field_found"] = True
                                metadata["test_field_value"] = actual_value
                                metadata["result"] = (
                                    f"""PARTIAL: TestField exists but wrong 
                                    value: """
                                    f"{actual_value}"
                                )
                                return (0.5, metadata)
                        else:
                            metadata["test_field_found"] = False
                            metadata["result"] = (
                                "FAIL: TestField not found in MODULE_ATTRS"
                            )
                            return (0.0, metadata)
                
                # MODULE_ATTRS not found
                metadata["error"] = "MODULE_ATTRS dict not found in __init__.py"
                return (0.0, metadata)
                
            except SyntaxError as e:
                metadata["error"] = f"Syntax error in __init__.py: {str(e)}"
                return (0.0, metadata)
                
        except Exception as e:
            metadata["error"] = f"Test failed: {str(e)}"
            return (0.0, metadata)


def test_grading(
    state: EnvironmentState,
    working_dir: str = "/workspace/vllm"
) -> Grade:
    """
    Grade the test task and check if TestField was added to MODULE_ATTRS.
    """
    return Grade.from_subscores([
        TestFieldGrader.grade(
            state=state,
            weight=1.0,
            working_dir=working_dir
        )
    ])