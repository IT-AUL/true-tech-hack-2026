import asyncio


async def test():
    from fastapi import Request
    from open_webui.tools.builtin import generate_presentation

    mock_request = Request({'type': 'http'})
    mock_user = {
        'id': '27876c96-35e0-4816-b13f-1218f7d00d92',
        'email': 'ranel-h@mail.ru',
        'name': 'dremotha',
        'role': 'admin',
    }

    slides = [{'title': 'Welcome', 'bullets': ['Hello', 'World'], 'notes': 'Testing'}]

    # We need to mock DB access or just see if it crashes before DB insertion.
    try:
        res = await generate_presentation(
            title='Test',
            slides_json=slides,
            theme='light',
            __request__=mock_request,
            __user__=mock_user,
            __chat_id__=None,
            __message_id__=None,
        )
        print('RESULT:')
        print(res)
    except Exception as e:
        print('EXCEPTION:', e)


asyncio.run(test())
