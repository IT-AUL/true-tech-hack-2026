with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py') as f:
    text = f.read()


# Look for the if function_calling_mode == 'native': block and add the else block back
search = """            if function_calling_mode == 'native':
                # Add file context to user messages for native function calling.
                chat_id = metadata.get('chat_id')
                form_data['messages'] = add_file_context(form_data.get('messages', []), chat_id, user)
                for name, tool_dict in builtin_tools.items():
                    if name not in tools_dict:
                        tools_dict[name] = tool_dict"""

replace = """            if function_calling_mode == 'native':
                # Add file context to user messages for native function calling.
                chat_id = metadata.get('chat_id')
                form_data['messages'] = add_file_context(form_data.get('messages', []), chat_id, user)
                for name, tool_dict in builtin_tools.items():
                    if name not in tools_dict:
                        tools_dict[name] = tool_dict
            else:
                for name in ('extract_file_content', 'generate_presentation', 'search_web'):
                    tool_dict = builtin_tools.get(name)
                    if tool_dict and name not in tools_dict:
                        tools_dict[name] = tool_dict"""

text = text.replace(search, replace)

with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py', 'w') as f:
    f.write(text)
