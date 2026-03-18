from langchain_core.messages import HumanMessage
from llm.openrouter_llm import ChatOpenRouter

google_model = ChatOpenRouter(
    model_name="google/gemini-2.5-flash",
).with_retry()


def make_image_call(text: str, image_encoded: str):
    message = HumanMessage(
        content=[
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_encoded}"},
            },
        ]
    )
    return google_model.invoke([message])
