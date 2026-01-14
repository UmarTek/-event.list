# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, User, Group, Event, init_database

# Инициализация базы данных при старте
init_database()

app = FastAPI(
    title="EventList API",
    description="API для управления группами и событиями",
    version="4.0.0"
)

# Импортируем роутеры ПОСЛЕ инициализации app
from api.auth import router as auth_router
from api.users import router as users_router
from api.groups import router as groups_router
from api.events import router as events_router
from api.moderation import router as moderation_router

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(events_router)
app.include_router(moderation_router)

@app.get("/")
async def root():
    return {
        "message": "EventList API работает!",
        "version": "4.0.0",
        "docs": "/docs",
        "status": "active"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)