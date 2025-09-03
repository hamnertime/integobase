from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from ... import models, schemas
from ...database import get_db

router = APIRouter()

# --- Article Endpoints ---

@router.post("/articles/", response_model=schemas.Article, status_code=status.HTTP_201_CREATED)
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
    """
    Create a new knowledge base article.
    """
    db_article = models.Article(**article.model_dump())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@router.get("/articles/", response_model=List[schemas.Article])
def read_articles(
    search: str = "",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all knowledge base articles with optional search and pagination.
    """
    query = db.query(models.Article).options(
        joinedload(models.Article.author),
        joinedload(models.Article.company)
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            models.Article.title.ilike(search_term) |
            models.Article.content.ilike(search_term)
        )

    articles = query.offset(skip).limit(limit).all()
    return articles

@router.get("/articles/{article_id}", response_model=schemas.Article)
def read_article(article_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single knowledge base article by its ID.
    """
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return db_article

@router.put("/articles/{article_id}", response_model=schemas.Article)
def update_article(article_id: int, article: schemas.ArticleUpdate, db: Session = Depends(get_db)):
    """
    Update an existing knowledge base article.
    """
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    update_data = article.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_article, key, value)

    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    """
    Delete a knowledge base article.
    """
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(db_article)
    db.commit()
    return {"ok": True}

# --- Category Endpoints ---

@router.post("/categories/", response_model=schemas.Category, status_code=status.HTTP_201_CREATED)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    """
    Create a new knowledge base category.
    """
    db_category = models.Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/categories/", response_model=List[schemas.Category])
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all knowledge base categories.
    """
    categories = db.query(models.Category).offset(skip).limit(limit).all()
    return categories

@router.put("/categories/{category_id}", response_model=schemas.Category)
def update_category(category_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    """
    Update an existing knowledge base category.
    """
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = category.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Delete a knowledge base category.
    """
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(db_category)
    db.commit()
    return {"ok": True}

