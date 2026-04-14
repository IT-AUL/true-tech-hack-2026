import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock env vars before import
os.environ['NEO4J_URI'] = 'bolt://neo4j:7687'
os.environ['NEO4J_USERNAME'] = 'neo4j'
os.environ['NEO4J_PASSWORD'] = 'password'

# Mock mem0.Memory because we don't want it to actually try to connect to Neo4j
import mem0
mem0.Memory = MagicMock()

try:
    from open_webui.memory.mem0_manager import _get_mem0_client
    client = _get_mem0_client()
    print("Mem0 client initialized (mocked)")
    
    # Check if from_config was called with expected dict structure
    args, kwargs = mem0.Memory.from_config.call_args
    config = args[0]
    
    print(f"Config provider: {config['graph_store']['provider']}")
    print(f"Config URL: {config['graph_store']['config']['url']}")
    
    if config['graph_store']['provider'] == 'neo4j' and config['graph_store']['config']['url'] == 'bolt://neo4j:7687':
        print("TEST PASSED: Configuration mapping is correct.")
    else:
        print("TEST FAILED: Configuration mismatch.")
        print(config)

except Exception as e:
    print(f"TEST FAILED: Exception occurred: {e}")
    import traceback
    traceback.print_exc()
