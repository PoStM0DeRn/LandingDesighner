from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_user
from app.models.schemas import Skill, SkillCreate
from app.storage.skills import list_skills, get_skill, create_skill, update_skill, delete_skill

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[Skill])
def get_all():
    return list_skills()


@router.get("/{skill_id}", response_model=Skill)
def get_one(skill_id: str):
    skill = get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.post("", response_model=Skill, status_code=201)
def create(data: SkillCreate, user: str = Depends(require_user)):
    return create_skill(data)


@router.put("/{skill_id}", response_model=Skill)
def update(skill_id: str, data: SkillCreate, user: str = Depends(require_user)):
    skill = update_skill(skill_id, data)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found or built-in")
    return skill


@router.delete("/{skill_id}", status_code=204)
def delete(skill_id: str, user: str = Depends(require_user)):
    if not delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill not found or built-in")
