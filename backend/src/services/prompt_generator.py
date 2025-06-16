import logging
from typing import Dict
import os
from dotenv import load_dotenv
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig

logger = logging.getLogger(__name__)

class PromptGenerator:
    """画像生成用のプロンプトを生成するサービス"""

    def __init__(self):
        # 環境変数の読み込み
        load_dotenv()
        self._initialize_vertex_ai()
        
        # プロンプト生成用のシステムプロンプト
        self.system_prompt = """
🎯 SYSTEM PROMPT: Create a single-sentence image generation prompt for Imagen 3

You are a prompt generation assistant.

Read the fantasy story text below and extract the **most visually striking scene** to generate a full-body anime-style illustration.  
This image represents the **final chapter of the season (結フェーズの最終話)**.

Then, write a **single English sentence prompt** (for Imagen 3) that describes the scene in detail.

---

### 📝 OUTPUT RULES

- Output exactly **one English sentence**
- Limit to **under 55 words**
- Start with: **light novel style fantasy anime illustration**
- End with a period
- Be clear, focused, and descriptive — no overcomplication or redundancy

---

### 👤 MAIN CHARACTER

- Age: early to mid 20s  
- Gender: male (mature and calm in appearance, not boyish)  
- Hair: short, slightly messy black hair  
- Eyes: sharp and focused  
- Expression: composed or resolute  
- Build: lean but athletic; clearly adult in height and form  
- Jawline: defined; facial features are subtly masculine  
- Outfit: light adventurer gear (cloth and leather, minimal metal)  
- Weapon: one-handed sword (may glow softly)  
- Optional: short cape, belt, or pouches

---

### 🧑‍🤝‍🧑 COMPANION (IF PRESENT)

- Include **only if clearly described** in the story  
- Max 1 companion  
- If named (e.g., Lulu), reflect implied traits (e.g., female mage with silver hair)  
- Must be visually distinct (hair, outfit, build) and **clearly supportive**  
- Do **not** depict companions cheering, clapping, or passively standing  
- Always show them **engaging in active support**, such as:
  - casting magic
  - wielding a weapon
  - defending or charging beside the protagonist

---

### ⚔️ ENEMY & ACTION SCENE RULES

- If an enemy appears, and the battle is ongoing or at its peak, **always prefer a dynamic battle scene** over a post-battle pose
- Choose one of the following:
  - Protagonist attacking, dodging, or unleashing magic  
  - Companion supporting with magic, ranged attacks, or synchronized moves  
- Avoid vague “mid-action” or unclear victory moments

**If the enemy is defeated**, clearly show the aftermath:
- Crumbling body, fading glow, shattered debris  
- Hero relaxing stance or holding sword aloft  
- Companion showing relief or celebration only if enemy is no longer present
Even if the story describes the moment just after victory, if a visible enemy is present, always depict an **ongoing battle scene** instead of a resolved moment.
- Treat all visible enemies as active threats, and illustrate the protagonist and companion mid-combat, delivering or preparing a final blow.

---

### 🖌️ VISUAL STYLE GUIDELINES

The illustration must follow a **modern Japanese light novel cover style**:

- 2D anime-style with clean lines and cel-shading  
- Soft ambient light, translucent colors  
- No 3D, heavy shadows, gritty or retro tones

As this is the final chapter, the background must depict a victorious moment — a climactic battle or its resolution.  
Avoid overusing the same background style (e.g., golden ruins).  
Use a variety of lighting and environments for diversity:

**Scene examples:**
- golden light over shattered ruins  
- twilight in a broken stone arena  
- moonlight on a cracked battlefield  
- morning sun through collapsed temple arches  
- red leaves swirling past fallen enemies  
- crystal-lit underground altar  
- snowy ruins glowing with magic light

Use combinations of landscape, lighting, and atmosphere to create a distinct final scene.

---

### 🔁 IF SCENE IS UNDERDESCRIBED

If the story lacks visual details, assume a **final battle or victorious aftermath**, and choose a clear moment:  
- Either the decisive strike (if the enemy is active)  
- Or a visually clear post-battle scene (if the enemy is defeated)  
Always prefer action over ambiguity.

---

### 🚫 PROHIBITED ELEMENTS

- No speech bubbles, text, UI, or manga-style overlays  
- No gore, blood, corpses, or fatal descriptors  
- Do not use: kill, slay, stab, corpse, blood, brutal, religious or sexualized terms
"""

    def _initialize_vertex_ai(self):
        """Vertex AIの初期化"""
        try:
            # 環境変数から設定を取得
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("VERTEX_AI_LOCATION", "asia-northeast1")
            model_name = os.getenv("VERTEX_AI_MODEL_NAME", "gemini-2.0-flash")
            
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT環境変数が設定されていません")
            
            # Vertex AIの初期化
            vertexai.init(
                project=project_id,
                location=location
            )
            
            # モデルの初期化
            self.model = GenerativeModel(model_name)
            
        except Exception as e:
            logger.error(f"Vertex AI初期化エラー: {str(e)}")
            raise

    async def generate_prompt(self, story_text: str) -> str:
        """
        ストーリーテキストから画像生成用のプロンプトを生成する

        Args:
            story_text (str): ストーリーテキスト

        Returns:
            str: 生成されたプロンプト
        """
        try:
            # 生成設定
            generation_config = GenerationConfig(
                temperature=0.7,  # 創造性と一貫性のバランスを取る
                max_output_tokens=256,  # 必要十分な長さ
                top_p=0.8,  # より多様な表現を許容
                top_k=40
            )
            
            # Vertex AIを使用してプロンプトを生成
            response = await self.model.generate_content_async(
                f"{self.system_prompt}\n\n【入力】\n描写: {story_text}",
                generation_config=generation_config
            )
            
            # 生成されたプロンプトを取得
            prompt = response.text.strip()
            print(f"prompt: {prompt}")
            
            return prompt

        except Exception as e:
            logger.error(f"プロンプト生成エラー: {str(e)}")
            raise Exception(f"プロンプト生成に失敗しました: {str(e)}") 