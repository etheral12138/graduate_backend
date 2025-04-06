from app.config import settings
from app.dependencies import get_supabase_client, get_embedding_model
from fastapi import APIRouter, HTTPException
import httpx
import numpy as np
from datetime import datetime

supabase_client = get_supabase_client()
model = get_embedding_model()
router = APIRouter(prefix="/quiz")


# 获取题目API
@router.get("/questions")
async def fetch_questions():
    try:
        query_params = {"apiKey": settings.QUIZ_API_KEY}
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.QUIZ_API_URL, params=query_params)
            response.raise_for_status()
            questions = response.json()
            # 2. 自动保存题目到Supabase
            session_data = supabase_client.table('quiz_sessions').insert([{
                'started_at': datetime.now().isoformat(),
                'question_count': len(questions),
                'status': 'in_progress'
            }]).execute()
            session_id = session_data.data[0]['id']
            questions_to_insert = [{
                'session_id': session_id,
                'question_id': q['id'],
                'question_text': q['question'],
                'description': q['description'],
                'category': q['category'],
                'difficulty': q['difficulty'],
                'answers': q['answers'],
                'correct_answers': q['correct_answers'],
                'explanation': q['explanation'],
                'tip': q['tip'],
                'tags': q['tags']
            } for q in questions]
            supabase_client.table('quiz_questions').insert(questions_to_insert).execute()
            return {
                "sessionId": session_data.data[0]['id'],
                "questions": questions
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 获取推荐题目
@router.get("/recommended-questions")
async def fetch_recommended_questions(limit: int = 10):
    try:
        # 1. 获取所有用户的历史答题记录
        all_answers = supabase_client.table('quiz_answers').select(
            'session_id, question_id, is_correct'
        ).order('answered_at', desc=True).limit(1000).execute().data
        # 2. 获取所有相关问题的详细信息
        question_ids = list(set([a['question_id'] for a in all_answers]))
        all_questions = supabase_client.table('quiz_questions').select('*').in_(
            'question_id', question_ids
        ).execute().data
        question_map = {q['question_id']: q for q in all_questions}
        answers_with_questions = [{
            **a,
            'quiz_questions': question_map.get(a['question_id'])
        } for a in all_answers]
        # 3. 为每个题目生成嵌入向量
        question_embeddings = {}
        # print([a['quiz_questions'] for a in answers_with_questions])
        unique_questions = list([a['quiz_questions'] for a in answers_with_questions])
        for question in unique_questions:
            text = f"题目：{question['question_text']} 分类：{question['category']} 难度：{question['difficulty']}"
            embedding = model.encode(text,
                                     normalize_embeddings=True,
                                     convert_to_tensor=True,  # 添加设备兼容
                                     )
            question_embeddings[question['question_id']] = embedding.cpu().numpy()  # 转换回numpy数组
        # 4. 获取当前用户的答题历史
        current_session = supabase_client.table('quiz_sessions').select(
            'id'
        ).order('started_at', desc=True).limit(1).single().execute().data
        user_answers = [a for a in all_answers if a['session_id'] == current_session['id']]
        # 5. 计算用户偏好向量
        user_preference = np.zeros(512)
        for answer in user_answers:
            question_id = answer['question_id']
            embedding = question_embeddings.get(question_id)
            if embedding is not None:
                weight = 1 if answer['is_correct'] else -0.5
                user_preference += embedding * weight
        # 6. 归一化用户偏好向量
        norm = np.linalg.norm(user_preference)
        if norm > 0:
            user_preference = user_preference / norm
        # 7. 计算所有题目与用户偏好的相似度
        question_scores = []
        for question_id, embedding in question_embeddings.items():
            if any(a['question_id'] == question_id for a in user_answers):
                continue
            similarity = np.dot(embedding, user_preference)
            question_scores.append({'question_id': question_id, 'score': similarity})
        # 8. 获取推荐题目ID
        question_scores.sort(key=lambda x: x['score'], reverse=True)
        recommended_ids = [q['question_id'] for q in question_scores[:limit]]
        # 9. 获取推荐题目的详细信息
        questions = supabase_client.table('quiz_questions').select('*').in_(
            'question_id', recommended_ids
        ).execute().data
        # 10. 返回格式化后的题目数据
        if questions:
            return [{
                'id': q['question_id'],
                'question': q['question_text'],
                'description': q['description'],
                'answers': q['answers'],
                'multiple_correct_answers': "false",
                'correct_answers': q['correct_answers'],
                'correct_answer': None,
                'explanation': q['explanation'],
                'tip': q['tip'],
                'tags': q['tags'],
                'category': q['category'],
                'difficulty': q['difficulty']
            } for q in questions]
    except Exception as e:
        print(f'获取推荐题目失败: {e}')


# 更新答题会话状态
@router.post("/sessions/{session_id}")
async def update_quiz_session(
        session_id: str,
        score: int = None,
        completed: bool = False
):
    try:
        # 构建更新数据
        update_data = {}
        if score is not None:
            update_data['score'] = score

        if completed:
            update_data['status'] = 'completed'
            update_data['completed_at'] = datetime.now().isoformat()
        else:
            update_data['status'] = 'in_progress'

        # 执行更新操作
        result = supabase_client.table('quiz_sessions').update(
            update_data
        ).eq('id', session_id).execute()

        # 检查更新结果
        if not result.data:
            raise HTTPException(status_code=404, detail="答题会话不存在或更新失败")

        return {"status": "success", "session_id": session_id, "updated_data": update_data}
    except Exception as e:
        print(f'更新答题会话状态失败: {e}')
        raise HTTPException(status_code=500, detail=f"更新会话状态失败: {str(e)}")


@router.post("/save-answer")
async def save_answer(
        session_id: str,
        question_id: int,
        selected_answer: str,
        is_correct: bool,
        answered_at: str
):
    try:
        # 插入答题记录到Supabase
        response = supabase_client.table('quiz_answers').insert([{
            'session_id': session_id,
            'question_id': question_id,
            'selected_answer': selected_answer,
            'is_correct': is_correct,
            'answered_at': answered_at
        }]).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="保存答题记录失败")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 获取用户答题历史会话
@router.get("/history")
async def get_quiz_history(user_id: str):
    try:
        # 查询用户的所有答题会话
        sessions = supabase_client.table('quiz_sessions').select(
            'id, started_at, question_count, status, score, completed_at'
        ).eq('user_id', user_id).order('started_at', desc=True).execute()

        if not sessions.data:
            return {"sessions": []}

        return {"sessions": sessions.data}
    except Exception as e:
        print(f'获取用户答题历史失败: {e}')
        raise HTTPException(status_code=500, detail="获取答题历史失败")


# 获取答题会话详情
@router.get("/session-detail")
async def get_session_detail(session_id: str):
    try:
        # 1. 获取会话基本信息
        session = supabase_client.table('quiz_sessions').select(
            'id, started_at, question_count, status, score, completed_at'
        ).eq('id', session_id).single().execute()

        if not session.data:
            raise HTTPException(status_code=404, detail="答题会话不存在")

        # 2. 获取该会话的所有答题记录
        answers_query = supabase_client.table('quiz_answers').select(
            'id, session_id, question_id, selected_answer, is_correct, answered_at'
        ).eq('session_id', session_id).execute()

        answers = answers_query.data

        # 3. 获取相关题目信息
        if answers:
            question_ids = [a['question_id'] for a in answers]
            questions = supabase_client.table('quiz_questions').select(
                'question_id, question_text'
            ).in_('question_id', question_ids).execute()

            question_map = {q['question_id']: q for q in questions.data}

            # 4. 合并答题记录和题目信息
            for answer in answers:
                question = question_map.get(answer['question_id'])
                if question:
                    answer['question_text'] = question['question_text']
                else:
                    answer['question_text'] = "题目信息不可用"

        return {
            "session": session.data,
            "answers": answers
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f'获取答题会话详情失败: {e}')
        raise HTTPException(status_code=500, detail="获取答题会话详情失败")
