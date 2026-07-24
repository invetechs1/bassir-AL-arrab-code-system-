"""Mandatory legal wording. Every user-facing output must carry this."""

DISCLAIMER_AR = (
    "هذا النظام يقدم مراجعة هندسية وتنظيمية أولية بمساعدة الذكاء الاصطناعي فقط. "
    "وهو ليس جهة اعتماد رسمية ولا يغني عن المهندسين المرخصين، أو الوثائق الرسمية "
    "لكود البناء السعودي، أو البلديات، أو الدفاع المدني، أو مزودي الخدمات، أو الجهات "
    "الحكومية. يجب التحقق من جميع المخرجات بواسطة مختصين مؤهلين قبل التقديم أو التنفيذ."
)

DISCLAIMER_EN = (
    "This system provides AI-assisted preliminary engineering and regulatory "
    "review only. It is not an official approval authority and does not replace "
    "licensed engineers, Saudi Building Code official documents, municipalities, "
    "Civil Defense, utility providers, or government authorities. All outputs "
    "must be verified by qualified professionals before submission or construction."
)


def disclaimer() -> dict:
    return {"ar": DISCLAIMER_AR, "en": DISCLAIMER_EN}
