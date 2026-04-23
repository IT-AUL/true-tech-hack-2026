
import sys
import os

# Add backend to path to import app modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

import asyncio
from unittest.mock import MagicMock
from open_webui.utils.tools import get_builtin_tools

async def main():
    print("Checking builtin tools registration...")
    
    # Mock request and other params
    request = MagicMock()
    request.app.state.config = MagicMock()
    request.app.state.config.ENABLE_WEB_SEARCH = True
    request.app.state.config.ENABLE_IMAGE_GENERATION = True
    request.app.state.config.ENABLE_CODE_INTERPRETER = True
    request.app.state.config.ENABLE_NOTES = True
    request.app.state.config.ENABLE_CHANNELS = True

    extra_params = {
        '__user__': {'id': 'test-user', 'role': 'admin'},
        '__event_emitter__': None,
        '__metadata__': {}
    }
    
    # Mock model info
    model = {
        'info': {
            'meta': {
                'capabilities': {'builtin_tools': True},
                'builtinTools': {} # Should default all to True
            }
        }
    }
    
    try:
        tools = get_builtin_tools(request, extra_params, features={}, model=model)
        
        print(f"Total tools found: {len(tools)}")
        print("Tools list:", list(tools.keys()))
        
        if 'generate_document' in tools:
            print("\n✅ SUCCESS: 'generate_document' is correctly registered!")
            spec = tools['generate_document']['spec']
            print("Tool Spec:", spec)
        else:
            print("\n❌ FAILURE: 'generate_document' NOT found in builtin tools.")
            
    except Exception as e:
        print(f"\n❌ ERROR during check: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
