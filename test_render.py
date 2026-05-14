import asyncio
from document_renderer_sdk import AsyncDocumentRendererClient

async def test():
    async with AsyncDocumentRendererClient() as client:
        response = await client.render_document(
            template_content="<h1>Тест PDF</h1><p>Данные: {{ name }}</p>", # Эту дичь надо поменять на адекватные данные
            data={"name": "Test Document"},
            filename="test_output.pdf",
            timeout=30
        )
        # URL на S3 получается через response.file_url
        # БАкет для хранилища можно задать в .env
        
asyncio.run(test())