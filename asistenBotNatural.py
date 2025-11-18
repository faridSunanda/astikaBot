import os, json, asyncio, re, random, time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# =============================
# KONFIGURASI UTAMA
# =============================
TOKEN = "7739470286:AAENQyesrOL6Bu7R1WMvfIFWiUlBOQ37O_k"  # Ganti dengan token bot kamu
USER_DATA_FILE = "user_data.json"

# =============================
# NATURAL CHATBOT CORE
# =============================
class NaturalChatbot:
    def __init__(self):
        # Memory systems
        self.conversation_history = defaultdict(lambda: deque(maxlen=10))
        self.user_profiles = defaultdict(self._create_user_profile)
        self.entity_memory = defaultdict(dict)
        
        # Personality settings
        self.personality = self._define_personality()
        self.response_templates = self._load_response_templates()
        
        # Proactive engine
        self.proactive_engine = ProactiveEngine()
        
        # Load existing data
        self._load_user_data()
    
    def _create_user_profile(self):
        """Create default user profile"""
        return {
            "name": None,
            "first_seen": datetime.now().isoformat(),
            "last_interaction": datetime.now().isoformat(),
            "interaction_count": 0,
            "preferred_tone": "adaptive",
            "topics_discussed": [],
            "personality_match": {
                "formality": 0.5,
                "enthusiasm": 0.7,
                "verbosity": 0.6,
                "humor": 0.4,
                "empathy": 0.8
            },
            "sentiment_history": deque(maxlen=10),
            "response_preferences": {
                "emoji_usage": True,
                "detailed_responses": False,
                "proactive_suggestions": True
            }
        }
    
    def _define_personality(self):
        """Define bot personality"""
        return {
            "name": "Asisten",
            "traits": ["helpful", "friendly", "patient", "knowledgeable", "empathetic"],
            "speaking_style": "conversational",
            "default_emoji_usage": "moderate",
            "adaptation_level": "high"
        }
    
    def _load_response_templates(self):
        """Load comprehensive response templates"""
        return {
            "greetings": {
                "morning": [
                    "Selamat pagi! ☀️ Semoga harimu menyenangkan. Ada yang bisa aku bantu?",
                    "Pagi! Ada rencana apa hari ini? Butuh bantuan?",
                    "Halo pagi! Ada yang ingin dibicarakan?",
                    "Selamat pagi! Mulai hari dengan semangat ya! Ada yang aku bantu?",
                    "Pagi! Jangan lupa sarapan dulu. Ada yang perlu dibantu?"
                ],
                "afternoon": [
                    "Selamat siang! Jangan lupa makan ya. Ada yang aku bantu?",
                    "Siang! Semangat jalani harinya. Butuh info apa?",
                    "Halo! Ada yang bisa aku bantu di siang hari ini?",
                    "Siang semua! Ada yang bisa aku bantu?",
                    "Selamat siang! Ada pertanyaan atau butuh bantuan?"
                ],
                "evening": [
                    "Selamat sore! Hari ini sudah produktif? Ada yang perlu dibantu?",
                    "Sore! Ada yang bisa aku bantu sebelum hari berakhir?",
                    "Halo sore! Ada pertanyaan atau butuh bantuan?",
                    "Selamat sore! Gimana harinya? Ada yang mau dibahas?",
                    "Sore! Ada yang bisa aku bantu sebelum pulang?"
                ],
                "night": [
                    "Selamat malam! Jangan begadang ya. Ada yang urgent?",
                    "Malam! Jangan lupa istirahat. Ada yang bisa aku bantu?",
                    "Halo malam! Ada yang penting perlu dibantu?",
                    "Selamat malam! Jangan terlalu larut ya. Ada yang bisa aku bantu?",
                    "Malam! Ada yang urgent perlu dibantu?"
                ]
            },
            "farewells": [
                "Sampai jumpa! Jangan ragu hubungi aku lagi ya 😊",
                "Baik, kalau ada apa-apa tinggal chat lagi!",
                "Oke, hati-hati di jalan ya! 👋",
                "Senang bisa membantu. Kapan lagi ya!",
                "See you! Take care! 💫",
                "Sampai bertemu lagi! Stay safe ya!",
                "Oke, kalau butuh bantuan tinggal chat aku lagi!"
            ],
            "acknowledgments": {
                "understanding": [
                    "Aku mengerti maksudmu...",
                    "Oh, begitu ya ceritanya...",
                    "Aku nih, aku paham...",
                    "Hmm, aku mengerti sekarang...",
                    "Oke, aku tangkep maksudnya...",
                    "Got it! Aku paham sekarang...",
                    "Oh iya, aku ngerti sekarang..."
                ],
                "thinking": [
                    "Hmm, tunggu sebentar ya aku pikirkan...",
                    "Oke, biar aku cari tahu dulu...",
                    "Tunggu ya, aku cek dulu infonya...",
                    "Moment ya, aku proses dulu...",
                    "Biarkan aku berpikir sejenak...",
                    "Tunggu bentar ya, aku cari dulu..."
                ],
                "empathy": [
                    "Aku mengerti perasaanmu...",
                    "Pasti itu tidak mudah ya...",
                    "Aku bisa bayangkan bagaimana rasanya...",
                    "Terima kasih sudah berbagi dengan aku...",
                    "Aku di sini untuk mendengarkan...",
                    "Itu pasti sulit ya...",
                    "Aku paham itu tidak mudah..."
                ],
                "agreement": [
                    "Betul sekali!",
                    "Aku setuju dengan itu.",
                    "Tepat sekali!",
                    "Ya, benar.",
                    "Persis seperti itu!",
                    "Iya, aku setuju...",
                    "Benar sekali!"
                ]
            },
            "helpful_responses": [
                "Ini yang bisa aku bantu: {suggestion}",
                "Coba ini ya: {suggestion}",
                "Mungkin ini bisa membantu: {suggestion}",
                "Aku punya ide, coba lihat: {suggestion}",
                "Begini cara aku bisa bantu: {suggestion}",
                "Menurutku ini bisa membantu: {suggestion}"
            ],
            "uncertainty_responses": [
                "Hmm, aku agak bingung dengan yang ini. Bisa dijelasin lagi?",
                "Maaf, aku belum paham maksudnya. Coba katakan dengan cara lain?",
                "Aku butuh klarifikasi lebih lanjut nih. Bisa detail lagi?",
                "Kurang mengerti, bisa diulang dengan kata-kata yang berbeda?",
                "Maaf, bisa tolong jelasin lagi? Aku mau bantu tapi belum ngeh.",
                "Aku kurang paham nih. Bisa dijelasin dengan cara lain?"
            ],
            "transition_phrases": [
                "Oh iya, tentang itu...",
                "Berbicara tentang hal lain...",
                "Ngomong-ngomong...",
                "Sambil kita tunggu...",
                "Sebagai informasi tambahan...",
                "Btw, aku ingat...",
                "Oh ya, hampir lupa..."
            ],
            "proactive_suggestions": [
                "Kayaknya kamu lagi butuh info tentang {topic}. Mau aku bantu?",
                "Aku perhatikan kamu sering tanya tentang {topic}. Ada yang spesifik?",
                "Mungkin ini bisa membantu dengan {topic} yang kamu cari...",
                "Tertarik dengan {topic}? Aku punya beberapa info nih...",
                "Soal {topic}, aku punya beberapa sumber yang mungkin berguna..."
            ],
            "emotional_responses": {
                "positive": [
                    "Senang mendengarnya! 😊",
                    "Wih, keren banget!",
                    "Mantap! Terus semangat ya!",
                    "Asik! Ada lagi yang mau dibahas?",
                    "Bagus sekali! Ada yang lain?",
                    "Great! Terus bagus ya!",
                    "Love to hear that! 😊"
                ],
                "negative": [
                    "Aku mengerti perasaanmu...",
                    "Pasti itu tidak mudah ya...",
                    "Aku di sini untuk mendengarkan...",
                    "Itu pasti sulit ya...",
                    "Aku paham itu tidak menyenangkan...",
                    "Terima kasih sudah berbagi...",
                    "Aku bisa bayangkan bagaimana rasanya..."
                ],
                "excited": [
                    "Wih, seru! Cerita lebih detail dong!",
                    "Asik! Aku ikut senang nih!",
                    "Mantap! Terus semangat ya!",
                    "Keren! Ada lagi yang seru?",
                    "Wow! That's awesome!",
                    "Exciting! Tell me more!"
                ],
                "worried": [
                    "Aku paham kalau kamu khawatir...",
                    "Tenang ya, aku bantu cari solusinya...",
                    "Itu pasti membuatmu cemas ya...",
                    "Aku di sini untuk membantu tenangkan...",
                    "Take it easy, kita cari jalan keluarnya...",
                    "Jangan terlalu khawatir, kita selesaikan bersama..."
                ]
            }
        }
    
    def _load_user_data(self):
        """Load existing user data"""
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, profile in data.items():
                        if user_id in self.user_profiles:
                            self.user_profiles[user_id].update(profile)
            except Exception as e:
                print(f"Error loading user data: {e}")
    
    def _save_user_data(self):
        """Save user data periodically"""
        try:
            data_to_save = {str(k): v for k, v in self.user_profiles.items()}
            with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving user data: {e}")
    
    def detect_time_greeting(self):
        """Detect time for appropriate greeting"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 15:
            return "afternoon"
        elif 15 <= hour < 19:
            return "evening"
        else:
            return "night"
    
    def analyze_message(self, message: str, user_id: str) -> Dict:
        """Analyze message for context and intent"""
        analysis = {
            "intent": None,
            "entities": [],
            "sentiment": "neutral",
            "urgency": "low",
            "complexity": "simple",
            "topics": [],
            "emotional_state": "calm",
            "question_type": None,
            "keywords": []
        }
        
        message_lower = message.lower()
        
        # Sentiment analysis
        positive_words = ["senang", "bagus", "keren", "mantap", "suka", "cinta", "hebat", "asik", "asyik", "wih", "wow", "great", "love", "happy"]
        negative_words = ["sedih", "marah", "kecewa", "benci", "jelek", "buruk", "payah", "gagal", "stress", "lelah", "capek", "pusing", "bete"]
        excited_words = ["waw", "keren", "mantap", "asik", "asyik", "wih", "seru", "luar biasa", "fantastis"]
        worried_words = ["khawatir", "cemas", "takut", "bimbang", "ragu", "gelisah"]
        
        pos_count = sum(1 for word in positive_words if word in message_lower)
        neg_count = sum(1 for word in negative_words if word in message_lower)
        exc_count = sum(1 for word in excited_words if word in message_lower)
        wor_count = sum(1 for word in worried_words if word in message_lower)
        
        # Determine emotional state
        if exc_count > pos_count and exc_count > 0:
            analysis["emotional_state"] = "excited"
            analysis["sentiment"] = "positive"
        elif wor_count > 0:
            analysis["emotional_state"] = "worried"
            analysis["sentiment"] = "negative"
        elif pos_count > neg_count:
            analysis["sentiment"] = "positive"
        elif neg_count > pos_count:
            analysis["sentiment"] = "negative"
        
        # Urgency detection
        urgent_words = ["segera", "cepat", "urgent", "penting", "darurat", "buru-buru", "sekarang", "secepatnya"]
        if any(word in message_lower for word in urgent_words):
            analysis["urgency"] = "high"
        
        # Complexity detection
        word_count = len(message.split())
        if word_count > 25:
            analysis["complexity"] = "complex"
        elif word_count > 12:
            analysis["complexity"] = "moderate"
        
        # Question type detection
        if "?" in message or any(word in message_lower for word in ["apa", "bagaimana", "mengapa", "kapan", "dimana", "siapa", "berapa"]):
            analysis["question_type"] = "direct_question"
        elif any(word in message_lower for word in ["bisa", "bantuan", "tolong", "help"]):
            analysis["question_type"] = "help_request"
        elif any(word in message_lower for word in ["mungkin", "kira-kira", "apa ya", "gimana ya"]):
            analysis["question_type"] = "uncertainty"
        
        # Extract keywords
        important_words = re.findall(r'\b\w+\b', message_lower)
        analysis["keywords"] = [word for word in important_words if len(word) > 3]
        
        return analysis
    
    def adapt_to_user(self, user_id: str, message: str, analysis: Dict):
        """Adapt bot personality to user style"""
        profile = self.user_profiles[user_id]
        personality = profile["personality_match"]
        
        # Detect formality level
        formal_words = ["bapak", "ibu", "saya", "anda", "terima kasih", "mohon"]
        casual_words = ["gue", "lo", "bro", "sis", "gan", "cuy", "makasih", "thanks"]
        
        message_lower = message.lower()
        
        if any(word in message_lower for word in formal_words):
            personality["formality"] = min(0.8, personality["formality"] + 0.1)
        elif any(word in message_lower for word in casual_words):
            personality["formality"] = max(0.2, personality["formality"] - 0.1)
        
        # Adapt enthusiasm based on user's emotional state
        if analysis["emotional_state"] == "excited":
            personality["enthusiasm"] = min(0.9, personality["enthusiasm"] + 0.1)
        elif analysis["emotional_state"] == "worried":
            personality["empathy"] = min(0.9, personality["empathy"] + 0.1)
        
        # Adapt verbosity based on message length
        if len(message.split()) > 20:
            personality["verbosity"] = min(0.8, personality["verbosity"] + 0.05)
        elif len(message.split()) < 8:
            personality["verbosity"] = max(0.3, personality["verbosity"] - 0.05)
        
        # Update sentiment history
        profile["sentiment_history"].append(analysis["sentiment"])
    
    def generate_natural_response(self, message: str, user_id: str, user_name: str = None) -> str:
        """Generate natural and contextual response"""
        # Analyze message
        analysis = self.analyze_message(message, user_id)
        
        # Get user profile
        profile = self.user_profiles[user_id]
        personality = profile["personality_match"]
        
        # Adapt to user style
        self.adapt_to_user(user_id, message, analysis)
        
        # Save to conversation history
        self.conversation_history[user_id].append({
            "timestamp": datetime.now(),
            "message": message,
            "analysis": analysis
        })
        
        # Update user interaction
        profile["last_interaction"] = datetime.now().isoformat()
        profile["interaction_count"] += 1
        
        # Generate response based on intent and context
        response = self._craft_response(message, analysis, user_name, personality, profile)
        
        # Add proactive suggestions occasionally
        if random.random() < 0.2 and profile["response_preferences"]["proactive_suggestions"]:
            proactive = self.proactive_engine.generate_proactive(user_id, self.conversation_history[user_id])
            if proactive:
                response += f"\n\n{proactive}"
        
        # Add emoji if appropriate
        if profile["response_preferences"]["emoji_usage"] and self._should_use_emoji(analysis, personality):
            response += self._add_appropriate_emoji(analysis["sentiment"])
        
        # Save data periodically
        if profile["interaction_count"] % 5 == 0:
            self._save_user_data()
        
        return response
    
    def _craft_response(self, message: str, analysis: Dict, user_name: str, personality: Dict, profile: Dict) -> str:
        """Craft appropriate response based on analysis"""
        message_lower = message.lower()
        
        # Handle greetings
        if any(word in message_lower for word in ["halo", "hai", "hi", "hello", "pagi", "siang", "sore", "malam"]):
            time_greeting = self.detect_time_greeting()
            greetings = self.response_templates["greetings"][time_greeting]
            response = random.choice(greetings)
            
            # Add personalization
            if user_name:
                response = response.replace("kamu", f"{user_name}")
            
            return response
        
        # Handle farewells
        if any(word in message_lower for word in ["bye", "selamat tinggal", "sampai jumpa", "dah", "dadah"]):
            farewells = self.response_templates["farewells"]
            return random.choice(farewells)
        
        # Handle help requests
        if analysis["question_type"] == "help_request":
            helpful_responses = self.response_templates["helpful_responses"]
            suggestions = [
                "coba cari di dokumentasi resmi",
                "tanya ke forum komunitas",
                "periksa pengaturan ulang",
                "hubungi support teknis",
                "coba restart dulu",
                "periksa koneksi internet"
            ]
            response = random.choice(helpful_responses).format(
                suggestion=random.choice(suggestions)
            )
            return response
        
        # Handle uncertainty
        if analysis["question_type"] == "uncertainty":
            acknowledgments = self.response_templates["acknowledgments"]["thinking"]
            clarification = self._ask_for_clarification()
            return random.choice(acknowledgments) + " " + clarification
        
        # Handle emotional responses
        if analysis["emotional_state"] in self.response_templates["emotional_responses"]:
            emotional_responses = self.response_templates["emotional_responses"][analysis["emotional_state"]]
            return random.choice(emotional_responses)
        
        # Handle general questions
        if analysis["question_type"] == "direct_question":
            # Simulate finding answer
            thinking_responses = self.response_templates["acknowledgments"]["thinking"]
            base_response = random.choice(thinking_responses)
            
            # Add simulated answer based on keywords
            if analysis["keywords"]:
                keyword = random.choice(analysis["keywords"])
                answer_templates = [
                    f"Menurut yang aku tahu tentang {keyword}, {self._generate_simulated_answer(keyword)}",
                    f"Soal {keyword}, kayaknya {self._generate_simulated_answer(keyword)}",
                    f"Tentang {keyword}, aku punya info: {self._generate_simulated_answer(keyword)}"
                ]
                base_response += " " + random.choice(answer_templates)
            
            return base_response
        
        # Default response based on sentiment
        if analysis["sentiment"] == "positive":
            return random.choice(self.response_templates["emotional_responses"]["positive"])
        elif analysis["sentiment"] == "negative":
            return random.choice(self.response_templates["emotional_responses"]["negative"])
        else:
            return self._generate_neutral_response(message, analysis, personality)
    
    def _generate_simulated_answer(self, keyword: str) -> str:
        """Generate simulated answer based on keyword"""
        simulated_answers = {
            "belajar": "penting untuk konsisten dan punya jadwal yang teratur",
            "kerja": "fokus pada prioritas dan jangan lupa istirahat",
            "kesehatan": "jaga pola makan dan olahraga teratur",
            "teknologi": "selalu update dengan perkembangan terbaru",
            "hubungan": "komunikasi yang baik adalah kuncinya",
            "keuangan": "buat anggaran dan investasi sejak dini",
            "waktu": "kelola dengan baik menggunakan teknik time management"
        }
        
        return simulated_answers.get(keyword, "aku butuh info lebih detail untuk jawab ini")
    
    def _generate_neutral_response(self, message: str, analysis: Dict, personality: Dict) -> str:
        """Generate neutral response"""
        # Check for common patterns
        if "apa kabar" in message.lower():
            return "Kabar aku baik, terima kasih! Kamu gimana? Ada yang bisa aku bantu?"
        
        if "lagi apa" in message.lower() or "sedang apa" in message.lower():
            return "Aku lagi siap membantu kamu! Ada yang perlu dibahas?"
        
        if "siapa kamu" in message.lower():
            return f"Aku {self.personality['name']}, asisten virtual yang siap bantu kamu. Ada yang bisa aku bantu?"
        
        # Default neutral responses
        neutral_responses = [
            "Oke, aku mengerti. Ada yang lain?",
            "Baik, sudah aku catat. Lanjut?",
            "Siap! Ada yang mau dibahas lagi?",
            "Noted! Ada pertanyaan lain?",
            "Oke! Butuh bantuan apa lagi?",
            "Mengerti. Ada yang bisa aku bantu lebih lanjut?"
        ]
        
        return random.choice(neutral_responses)
    
    def _ask_for_clarification(self) -> str:
        """Ask for clarification naturally"""
        clarifications = [
            "bisa jelasin lebih detail lagi?",
            "ada bagian yang spesifik yang bikin bingung?",
            "coba kasih contohnya ya",
            "mulai dari mana yang kurang jelas?",
            "ada konteks lain yang perlu aku tahu?",
            "bisa dijelasin dengan cara lain?"
        ]
        
        return random.choice(clarifications)
    
    def _should_use_emoji(self, analysis: Dict, personality: Dict) -> bool:
        """Determine if emoji should be used"""
        if personality["formality"] > 0.7:
            return False
        
        if analysis["emotional_state"] == "excited":
            return random.random() < 0.8
        elif analysis["emotional_state"] == "worried":
            return random.random() < 0.3
        elif analysis["sentiment"] == "positive":
            return random.random() < 0.6
        else:
            return random.random() < 0.3
    
    def _add_appropriate_emoji(self, sentiment: str) -> str:
        """Add appropriate emoji based on sentiment"""
        emoji_map = {
            "positive": ["😊", "👍", "✨", "🎉", "💫"],
            "negative": ["🤗", "💪", "🙏", "❤️"],
            "neutral": ["🙂", "👌", "🤔", "💡"]
        }
        
        emojis = emoji_map.get(sentiment, emoji_map["neutral"])
        return " " + random.choice(emojis)
    
    def add_contextual_followup(self, user_id: str) -> Optional[str]:
        """Add contextual follow-up"""
        history = list(self.conversation_history[user_id])
        
        if len(history) >= 2:
            last_topic = history[-2]["message"]
            last_analysis = history[-2]["analysis"]
            
            # Follow-up based on topic
            if "deadline" in last_topic.lower():
                followups = ["Bagaimana progressnya?", "Sudah ada kemajuan?", "Butuh bantu manage waktu?"]
                return random.choice(followups)
            elif "belajar" in last_topic.lower():
                followups = ["Ada materi yang sulit?", "Butuh referensi tambahan?", "Sudah ada kemajuan?"]
                return random.choice(followups)
            elif last_analysis["sentiment"] == "negative":
                followups = ["Sekarang gimana kondisinya?", "Ada yang bisa aku bantu?", "Sudah lebih baik?"]
                return random.choice(followups)
        
        return None

# =============================
# PROACTIVE ENGINE
# =============================
class ProactiveEngine:
    def __init__(self):
        self.proactive_triggers = {
            "time_based": self._time_based_proactive,
            "pattern_based": self._pattern_based_proactive,
            "emotion_based": self._emotion_based_proactive
        }
    
    def generate_proactive(self, user_id: str, conversation_history: deque) -> Optional[str]:
        """Generate proactive suggestion"""
        # Time-based proactive
        time_suggestion = self._time_based_proactive()
        if time_suggestion and random.random() < 0.3:
            return time_suggestion
        
        # Pattern-based proactive
        if len(conversation_history) > 3:
            pattern_suggestion = self._pattern_based_proactive(conversation_history)
            if pattern_suggestion:
                return pattern_suggestion
        
        return None
    
    def _time_based_proactive(self) -> Optional[str]:
        """Time-based proactive suggestions"""
        hour = datetime.now().hour
        
        if hour == 9:
            return "Pagi! Ada planning buat hari ini? Mungkin aku bisa bantu."
        elif hour == 12:
            return "Siang! Jangan lupa makan ya. Ada yang perlu dibantu?"
        elif hour == 18:
            return "Sore! Gimana harinya? Ada achievement yang mau dibagi?"
        elif hour == 21:
            return "Malam! Jangan lupa istirahat ya. Ada yang urgent besok?"
        
        return None
    
    def _pattern_based_proactive(self, conversation_history: deque) -> Optional[str]:
        """Pattern-based proactive suggestions"""
        recent_topics = []
        recent_sentiments = []
        
        for entry in list(conversation_history)[-3:]:
            message = entry["message"].lower()
            analysis = entry["analysis"]
            
            if "deadline" in message:
                recent_topics.append("deadline")
            elif "belajar" in message or "study" in message:
                recent_topics.append("study")
            elif "kerja" in message or "work" in message:
                recent_topics.append("work")
            
            recent_sentiments.append(analysis["sentiment"])
        
        # Suggest based on patterns
        if "deadline" in recent_topics:
            return "Kayaknya lagi banyak deadline ya. Butuh bantu manage waktu?"
        elif "study" in recent_topics:
            return "Lagi belajar intens ya? Butuh referensi atau bantuan konsep?"
        elif all(s == "negative" for s in recent_sentiments):
            return "Aku perhatikan kamu kayaknya lagi tidak baik-baik saja. Ada yang mau dibicarain?"
        
        return None
    
    def _emotion_based_proactive(self, user_id: str, sentiment_history: deque) -> Optional[str]:
        """Emotion-based proactive suggestions"""
        if len(sentiment_history) > 2:
            recent_sentiments = list(sentiment_history)[-3:]
            
            if all(s == "negative" for s in recent_sentiments):
                return "Aku perhatikan kamu kayaknya lagi tidak baik-baik saja. Ada yang mau dibicarain?"
        
        return None

# =============================
# TELEGRAM BOT INTEGRATION
# =============================
class TelegramNaturalBot:
    def __init__(self, token: str):
        self.token = token
        self.chatbot = NaturalChatbot()
        self.typing_tasks = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Update user profile
        self.chatbot.user_profiles[user_id]["name"] = user_name
        
        # Check if returning user
        if self.chatbot.user_profiles[user_id]["interaction_count"] > 0:
            greeting = (
                f"Selamat datang kembali, {user_name}! 👋\n\n"
                "Senang bisa ngobrol sama kamu lagi. "
                "Aku sudah belajar banyak dari percakapan kita sebelumnya! 😊\n\n"
                "Ada yang mau dibahas hari ini?"
            )
        else:
            greeting = (
                f"Halo {user_name}! 👋\n\n"
                "Aku asisten virtual yang siap membantu kamu. "
                "Bisa tanya apa aja, ngobrol santai juga boleh! 😊\n\n"
                "Aku bakal berusaha ngobrol se-natural mungkin, "
                "jadi jangan ragu ya buat ngobrol sama aku!"
            )
        
        await self._simulate_typing(update, context)
        await update.message.reply_text(greeting)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for text messages"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        message = update.message.text
        
        # Simulate typing for natural effect
        await self._simulate_typing(update, context)
        
        # Generate response
        response = self.chatbot.generate_natural_response(message, user_id, user_name)
        
        # Add contextual follow-up occasionally
        if random.random() < 0.2:
            follow_up = self.chatbot.add_contextual_followup(user_id)
            if follow_up:
                response += f"\n\n{follow_up}"
        
        # Send response
        await update.message.reply_text(response)
        
        # Randomly send additional emoji for natural effect
        if random.random() < 0.1:
            await self._send_random_emoji(update, context)
    
    async def _simulate_typing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Simulate typing indicator"""
        chat_id = update.effective_chat.id
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            # Random delay for natural effect
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
        except Exception as e:
            print(f"Error simulating typing: {e}")
    
    async def _send_random_emoji(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send random emoji for natural effect"""
        emojis = ["😊", "👍", "🤔", "💡", "✨", "🌟", "🎯", "💪", "🙌", "👋"]
        emoji = random.choice(emojis)
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=emoji
            )
        except Exception as e:
            print(f"Error sending emoji: {e}")
    
    def run(self):
        """Run the bot"""
        app = ApplicationBuilder().token(self.token).build()
        
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        print("🤖 Natural Chatbot Assistant sedang berjalan...")
        print("Bot akan beradaptasi dengan gaya bahasa kamu!")
        app.run_polling()

# =============================
# MAIN EXECUTION
# =============================
if __name__ == "__main__":
    # Check if token is provided
    if TOKEN == "YOUR_TELEGRAM_TOKEN_HERE":
        print("⚠️  Error: Token belum diset!")
        print("Ganti 'YOUR_TELEGRAM_TOKEN_HERE' dengan token bot kamu")
        exit(1)
    
    # Initialize and run bot
    bot = TelegramNaturalBot(TOKEN)
    bot.run()