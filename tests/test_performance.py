import time
import os
from testdatagen.cli import main

FILES = ["ecommerce", "minimal",  "edge_cases", "complex_refs"]

def _performance_helper(runner, schema_dir, file_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    start = time.time()
    result = runner.invoke(main, [
        'generate', 
        schema_path, 
        '--output', str(schema_dir), 
        '--format', 'sql,json,report'
    ])
    end = time.time()
    
    assert result.exit_code == 0
    duration = end - start
    print(f"\nGeneration time: {duration:.2f}s")
    assert duration < 15

def test_performance_complex_refs(runner, schema_dir):
    for example in FILES:
        _performance_helper(runner, schema_dir, example)