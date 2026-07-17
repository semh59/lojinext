"""Generate a short LLM insight for an anomaly cluster (Groq)."""


async def generate_cluster_insight(cluster: dict) -> str:
    """Groq ile küme için kısa Türkçe insight. Hata → caller yutar."""
    from v2.modules.ai_assistant.infrastructure.llm.groq_client import GroqService

    prompt = (
        f"Filo anomali kümesi: {cluster['label']}. "
        f"Severity dağılımı: {cluster['severity_dagilim']}. "
        "Tek cümlede olası kök neden ve önerilen aksiyonu Türkçe yaz."
    )
    return await GroqService().chat(prompt, system_prompt="Sen bir filo analistisin.")
