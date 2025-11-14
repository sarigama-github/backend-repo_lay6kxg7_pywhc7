import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from bson import ObjectId

from database import create_document, get_documents, db

app = FastAPI(title="Architecture Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Helpers ---------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id") is not None:
        d["id"] = str(d.pop("_id"))
    # Convert any ObjectIds inside arrays
    for k, v in d.items():
        if isinstance(v, ObjectId):
            d[k] = str(v)
        if isinstance(v, list):
            d[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
    return d


# --------- Schemas (Pydantic) ---------
class WorkBase(BaseModel):
    title: str = Field(..., description="Project title")
    description: Optional[str] = Field(None, description="Short description")
    year: Optional[int] = Field(None, ge=1900, le=2100)
    location: Optional[str] = None
    cover_image: Optional[str] = None
    gallery: Optional[List[str]] = Field(default_factory=list)


class WorkCreate(WorkBase):
    pass


class WorkOut(WorkBase):
    id: str


# --------- Routes ---------
@app.get("/", tags=["root"])
def read_root():
    return {"message": "Architecture Portfolio Backend is running"}


@app.get("/test", tags=["health"])
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", None) or "❌ Unknown"
            # Try list collections
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response


@app.post("/api/works", response_model=WorkOut, tags=["works"])
def create_work(payload: WorkCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    work_id = create_document("work", payload.model_dump())
    # Fetch inserted document to return fully
    inserted = db["work"].find_one({"_id": ObjectId(work_id)})
    return serialize_doc(inserted)


@app.get("/api/works", response_model=List[WorkOut], tags=["works"])
def list_works(limit: Optional[int] = 100):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    docs = get_documents("work", {}, limit=limit)
    return [serialize_doc(d) for d in docs]


@app.get("/api/works/{work_id}", response_model=WorkOut, tags=["works"])
def get_work(work_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    if not ObjectId.is_valid(work_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    doc = db["work"].find_one({"_id": ObjectId(work_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
