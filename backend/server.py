from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime, timezone
from google import genai
from google.genai import types
from groq import AsyncGroq
from passlib.context import CryptContext
from jose import jwt, JWTError


import certifi

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, tls=True, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Auth Conf ---
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "super-secret-key-for-dev")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return user

SYSTEM_MESSAGE = """You are a healthcare educational assistant. Analyze symptoms and respond with ONLY a valid JSON object (no markdown, no code blocks, just raw JSON).

The JSON must contain:
{
  "is_emergency": false,
  "conditions": [
    {
      "name": "Condition Name",
      "description": "Brief 1-2 sentence description of the condition.",
      "likelihood": "high" | "medium" | "low"
    }
  ],
  "next_steps": [
    "Step 1 description",
    "Step 2 description"
  ],
  "disclaimer": "This information is for educational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider."
}

Rules:
- Set "is_emergency": true ONLY if symptoms indicate a potentially life-threatening or severe situation requiring immediate emergency medical care (e.g., chest pain, stroke signs).
- Provide 3-5 conditions sorted by likelihood (high first)
- Provide 3-5 actionable next steps
- Never make definitive diagnoses
- Always recommend consulting a healthcare professional
- Respond ONLY with raw JSON, absolutely no other text"""


# --- Pydantic Models ---
class UserCreate(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    age: int
    gender: str
    pre_existing_conditions: str = ""

class Token(BaseModel):
    access_token: str
    token_type: str

class SymptomInput(BaseModel):
    symptoms: str


class Condition(BaseModel):
    name: str
    description: str
    likelihood: str


class SymptomCheckResponse(BaseModel):
    id: str
    symptoms: str
    is_emergency: bool = False
    conditions: List[Condition]
    next_steps: List[str]
    disclaimer: str
    created_at: str


# --- Helper ---
def doc_to_response(doc: dict) -> SymptomCheckResponse:
    created = doc.get("created_at", "")
    if isinstance(created, datetime):
        created = created.isoformat()
    return SymptomCheckResponse(
        id=doc["id"],
        symptoms=doc["symptoms"],
        is_emergency=doc.get("is_emergency", False),
        conditions=[Condition(**c) for c in doc["conditions"]],
        next_steps=doc["next_steps"],
        disclaimer=doc["disclaimer"],
        created_at=created,
    )


def clean_and_parse_llm_json(response_text: str) -> dict:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


async def generate_with_gemini(prompt: str) -> str:
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY missing")

    client = genai.Client(api_key=gemini_key)
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_MESSAGE),
    )
    return response.text or ""


async def generate_with_groq(prompt: str) -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY missing")

    client = AsyncGroq(api_key=groq_key)
    completion = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content or ""


# --- Routes ---
@api_router.get("/")
async def root():
    return {"message": "Healthcare Symptom Checker API"}

@api_router.post("/auth/register")
async def register_user(user: UserCreate):
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    user_doc = {
        "id": str(uuid.uuid4()),
        "username": user.username,
        "hashed_password": hashed_password
    }
    await db.users.insert_one(user_doc)
    return {"message": "User registered successfully"}

@api_router.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.users.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}


@api_router.get("/user/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    profile = current_user.get("profile", {})
    return UserProfile(
        age=profile.get("age", 0),
        gender=profile.get("gender", ""),
        pre_existing_conditions=profile.get("pre_existing_conditions", "")
    )

@api_router.post("/user/profile")
async def update_profile(profile: UserProfile, current_user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"profile": profile.model_dump()}}
    )
    return {"message": "Profile updated successfully"}


@api_router.post("/symptoms/check", response_model=SymptomCheckResponse)
async def check_symptoms(input: SymptomInput, current_user: dict = Depends(get_current_user)):
    if not input.symptoms or len(input.symptoms.strip()) < 5:
        raise HTTPException(status_code=400, detail="Please provide a meaningful symptom description.")

    try:
        prompt = f"Based on these symptoms, suggest possible conditions and next steps with educational disclaimer: {input.symptoms}"
        profile = current_user.get("profile")
        if profile and profile.get("age") and profile.get("gender"):
            patient_context = f"Patient context: {profile.get('age')} year old {profile.get('gender')}. Pre-existing conditions: {profile.get('pre_existing_conditions', 'None reported')}."
            prompt = f"{patient_context}\n\n{prompt}"
            logger.info(f"Injecting medical profile into prompt: {patient_context}")
        response_text = ""
        parsed = None
        llm_errors = []

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            for attempt in range(1, 3):
                try:
                    response_text = await generate_with_gemini(prompt)
                    logger.info(f"Gemini raw response: {response_text[:200]}")
                    parsed = clean_and_parse_llm_json(response_text)
                    logger.info("Generated symptom analysis using Gemini")
                    break
                except Exception as e:
                    llm_errors.append(f"Gemini attempt {attempt}: {e}")
                    logger.warning(f"Gemini attempt {attempt} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1.5)

        if parsed is None and os.environ.get("GROQ_API_KEY"):
            try:
                response_text = await generate_with_groq(prompt)
                logger.info(f"Groq raw response: {response_text[:200]}")
                parsed = clean_and_parse_llm_json(response_text)
                logger.info("Generated symptom analysis using Groq fallback")
            except Exception as e:
                llm_errors.append(f"Groq fallback: {e}")
                logger.warning(f"Groq fallback failed: {e}")

        if parsed is None:
            joined_errors = " | ".join(llm_errors) if llm_errors else "No LLM providers configured."
            raise HTTPException(
                status_code=503,
                detail=f"AI providers are currently unavailable. {joined_errors}",
            )

        is_emergency = parsed.get("is_emergency", False)
        conditions = [Condition(**c) for c in parsed.get("conditions", [])]
        next_steps = parsed.get("next_steps", [])
        disclaimer = parsed.get("disclaimer", "This information is for educational purposes only.")

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} | response: {response_text}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response. Please try again.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "id": record_id,
        "user_id": current_user["id"],
        "symptoms": input.symptoms,
        "is_emergency": is_emergency,
        "conditions": [c.model_dump() for c in conditions],
        "next_steps": next_steps,
        "disclaimer": disclaimer,
        "created_at": now.isoformat(),
    }
    await db.symptom_checks.insert_one(doc)

    return SymptomCheckResponse(
        id=record_id,
        symptoms=input.symptoms,
        is_emergency=is_emergency,
        conditions=conditions,
        next_steps=next_steps,
        disclaimer=disclaimer,
        created_at=now.isoformat(),
    )


@api_router.get("/history", response_model=List[SymptomCheckResponse])
async def get_history(current_user: dict = Depends(get_current_user)):
    docs = await db.symptom_checks.find({"user_id": current_user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [doc_to_response(d) for d in docs]


@api_router.get("/history/{check_id}", response_model=SymptomCheckResponse)
async def get_history_item(check_id: str, current_user: dict = Depends(get_current_user)):
    doc = await db.symptom_checks.find_one({"id": check_id, "user_id": current_user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found.")
    return doc_to_response(doc)


@api_router.delete("/history/{check_id}")
async def delete_history_item(check_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.symptom_checks.delete_one({"id": check_id, "user_id": current_user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Record not found.")
    return {"message": "Deleted successfully."}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
