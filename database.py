import os
import psycopg2
import streamlit as st
import json
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from psycopg2.extras import RealDictCursor

# تكوين اتصال قاعدة البيانات من متغيرات البيئة
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('NEON_HOST'),
        database=os.getenv('NEON_DATABASE'),
        user=os.getenv('NEON_USER'),
        password=os.getenv('NEON_PASSWORD'),
        sslmode='require'
    )

def init_db():
    """تهيئة جداول قاعدة البيانات إذا لم تكن موجودة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # إنشاء جدول المحافظات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Governorates (
                governorate_id SERIAL PRIMARY KEY,
                governorate_name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        ''')
        
        # إنشاء جدول الإدارات الصحية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS HealthAdministrations (
                admin_id SERIAL PRIMARY KEY,
                admin_name TEXT NOT NULL,
                description TEXT,
                governorate_id INTEGER NOT NULL REFERENCES Governorates(governorate_id),
                UNIQUE(admin_name, governorate_id)
            )
        ''')
        
        # إنشاء جدول المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                user_id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                assigned_region INTEGER REFERENCES HealthAdministrations(admin_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                last_activity TIMESTAMP
            )
        ''')
        
        # إنشاء جدول الاستبيانات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Surveys (
                survey_id SERIAL PRIMARY KEY,
                survey_name TEXT NOT NULL,
                created_by INTEGER NOT NULL REFERENCES Users(user_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # إنشاء جدول حقول الاستبيان
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Survey_Fields (
                field_id SERIAL PRIMARY KEY,
                survey_id INTEGER NOT NULL REFERENCES Surveys(survey_id),
                field_type TEXT NOT NULL,
                field_label TEXT NOT NULL,
                field_options TEXT,
                is_required BOOLEAN DEFAULT FALSE,
                field_order INTEGER NOT NULL
            )
        ''')
        
        # إنشاء جدول الإجابات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Responses (
                response_id SERIAL PRIMARY KEY,
                survey_id INTEGER NOT NULL REFERENCES Surveys(survey_id),
                user_id INTEGER NOT NULL REFERENCES Users(user_id),
                region_id INTEGER NOT NULL REFERENCES HealthAdministrations(admin_id),
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # إنشاء جدول تفاصيل الإجابات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Response_Details (
                detail_id SERIAL PRIMARY KEY,
                response_id INTEGER NOT NULL REFERENCES Responses(response_id),
                field_id INTEGER NOT NULL REFERENCES Survey_Fields(field_id),
                answer_value TEXT
            )
        ''')
        
        # إنشاء جدول مسؤولي المحافظات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS GovernorateAdmins (
                admin_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES Users(user_id),
                governorate_id INTEGER NOT NULL REFERENCES Governorates(governorate_id),
                UNIQUE(user_id, governorate_id)
            )
        ''')
        
        # إنشاء جدول الاستبيانات المسموحة للمستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS UserSurveys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES Users(user_id),
                survey_id INTEGER NOT NULL REFERENCES Surveys(survey_id),
                UNIQUE(user_id, survey_id)
            )
        ''')
        
        # إنشاء جدول المحافظات المسموحة للاستبيانات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS SurveyGovernorate (
                id SERIAL PRIMARY KEY,
                survey_id INTEGER NOT NULL REFERENCES Surveys(survey_id),
                governorate_id INTEGER NOT NULL REFERENCES Governorates(governorate_id),
                UNIQUE(survey_id, governorate_id)
            )
        ''')
        
        # إنشاء جدول سجل التعديلات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS AuditLog (
                log_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES Users(user_id),
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # إضافة مستخدم المسؤول إذا لم يكن موجوداً
        cursor.execute("SELECT COUNT(*) FROM Users WHERE role='admin'")
        if cursor.fetchone()[0] == 0:
            from auth import hash_password
            admin_password = hash_password("admin123")
            cursor.execute(
                "INSERT INTO Users (username, password_hash, role) VALUES (%s, %s, %s)",
                ("admin", admin_password, "admin")
            )
        
        conn.commit()
        
    except Exception as e:
        st.error(f"حدث خطأ في تهيئة قاعدة البيانات: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# دوال المستخدمين
def get_user_by_username(username: str) -> Optional[Dict]:
    """الحصول على بيانات المستخدم باستخدام اسم المستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM Users WHERE username=%s", (username,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب بيانات المستخدم: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_role(user_id: int) -> Optional[str]:
    """الحصول على دور المستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM Users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        st.error(f"حدث خطأ في جلب دور المستخدم: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def update_last_login(user_id: int) -> bool:
    """تحديث وقت آخر دخول للمستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث وقت الدخول: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def update_user_activity(user_id: int) -> bool:
    """تحديث وقت آخر نشاط للمستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث وقت النشاط: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def add_user(username: str, password: str, role: str, region_id: int = None) -> bool:
    """إضافة مستخدم جديد"""
    from auth import hash_password
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM Users WHERE username=%s", (username,))
        if cursor.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        cursor.execute(
            "INSERT INTO Users (username, password_hash, role, assigned_region) VALUES (%s, %s, %s, %s)",
            (username, hash_password(password), role, region_id))
        
        conn.commit()
        st.success("تمت إضافة المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في إضافة المستخدم: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_user(user_id: int, username: str, role: str, region_id: int = None) -> bool:
    """تحديث بيانات المستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, role, assigned_region FROM Users WHERE user_id=%s", (user_id,))
        old_data = cursor.fetchone()
        
        cursor.execute("SELECT 1 FROM Users WHERE username=%s AND user_id!=%s", (username, user_id))
        if cursor.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        cursor.execute(
            "UPDATE Users SET username=%s, role=%s, assigned_region=%s WHERE user_id=%s",
            (username, role, region_id, user_id)
        )
        
        if role == 'governorate_admin':
            cursor.execute("DELETE FROM GovernorateAdmins WHERE user_id=%s", (user_id,))
            
        conn.commit()
        
        # تسجيل التعديل في سجل التعديلات
        new_data = (username, role, region_id)
        changes = {
            'username': {'old': old_data[0], 'new': new_data[0]},
            'role': {'old': old_data[1], 'new': new_data[1]},
            'assigned_region': {'old': old_data[2], 'new': new_data[2]}
        }
        log_audit_action(
            st.session_state.user_id, 
            'UPDATE', 
            'Users', 
            user_id,
            old_data,
            new_data
        )
        
        st.success("تم تحديث بيانات المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث المستخدم: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# دوال المحافظات والإدارات الصحية
def get_governorates_list() -> List[Tuple]:
    """الحصول على قائمة المحافظات"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT governorate_id, governorate_name FROM Governorates")
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب قائمة المحافظات: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def add_health_admin(admin_name: str, description: str, governorate_id: int) -> bool:
    """إضافة إدارة صحية جديدة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM HealthAdministrations WHERE admin_name=%s AND governorate_id=%s", 
                     (admin_name, governorate_id))
        if cursor.fetchone():
            st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
            return False
        
        cursor.execute(
            "INSERT INTO HealthAdministrations (admin_name, description, governorate_id) VALUES (%s, %s, %s)",
            (admin_name, description, governorate_id)
        )
        conn.commit()
        st.success(f"تمت إضافة الإدارة الصحية '{admin_name}' بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في إضافة الإدارة الصحية: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_health_admins() -> List[Tuple]:
    """الحصول على قائمة الإدارات الصحية"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT admin_id, admin_name FROM HealthAdministrations")
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب الإدارات الصحية: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_health_admin_name(admin_id: int) -> str:
    """الحصول على اسم الإدارة الصحية"""
    if admin_id is None:
        return "غير معين"
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT admin_name FROM HealthAdministrations WHERE admin_id=%s", (admin_id,))
        result = cursor.fetchone()
        return result[0] if result else "غير معروف"
    except Exception as e:
        st.error(f"حدث خطأ في جلب اسم الإدارة الصحية: {str(e)}")
        return "خطأ في النظام"
    finally:
        if conn:
            conn.close()

# دوال مسؤولي المحافظات
def add_governorate_admin(user_id: int, governorate_id: int) -> bool:
    """إضافة مسؤول محافظة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (%s, %s)",
            (user_id, governorate_id)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"خطأ في إضافة مسؤول المحافظة: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_governorate_admin(user_id: int) -> List[Tuple]:
    """الحصول على بيانات مسؤول المحافظة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT g.governorate_id, g.governorate_name 
            FROM GovernorateAdmins ga
            JOIN Governorates g ON ga.governorate_id = g.governorate_id
            WHERE ga.user_id = %s
        ''', (user_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب بيانات مسؤول المحافظة: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_governorate_admin_data(user_id: int) -> Optional[Tuple]:
    """الحصول على بيانات مسؤول المحافظة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT g.governorate_id, g.governorate_name, g.description 
            FROM GovernorateAdmins ga
            JOIN Governorates g ON ga.governorate_id = g.governorate_id
            WHERE ga.user_id = %s
        ''', (user_id,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب بيانات المحافظة: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def get_governorate_surveys(governorate_id: int) -> List[Tuple]:
    """الحصول على استبيانات المحافظة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.survey_id, s.survey_name, s.created_at, s.is_active
            FROM Surveys s
            JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
            WHERE sg.governorate_id = %s
            ORDER BY s.created_at DESC
        ''', (governorate_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب استبيانات المحافظة: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_governorate_employees(governorate_id: int) -> List[Tuple]:
    """الحصول على موظفي المحافظة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.user_id, u.username, ha.admin_name
            FROM Users u
            JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
            WHERE ha.governorate_id = %s AND u.role = 'employee'
            ORDER BY u.username
        ''', (governorate_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب موظفي المحافظة: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

# دوال الاستبيانات
def save_survey(survey_name: str, fields: List[Dict], governorate_ids: List[int] = None) -> bool:
    """حفظ استبيان جديد"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. حفظ الاستبيان الأساسي
        cursor.execute(
            "INSERT INTO Surveys (survey_name, created_by) VALUES (%s, %s) RETURNING survey_id",
            (survey_name, st.session_state.user_id)
        )
        survey_id = cursor.fetchone()[0]
        
        # 2. ربط الاستبيان بالمحافظات
        if governorate_ids:
            for gov_id in governorate_ids:
                cursor.execute(
                    "INSERT INTO SurveyGovernorate (survey_id, governorate_id) VALUES (%s, %s)",
                    (survey_id, gov_id)
                )
        
        # 3. حفظ حقول الاستبيان
        for i, field in enumerate(fields):
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            cursor.execute(
                """INSERT INTO Survey_Fields 
                   (survey_id, field_type, field_label, field_options, is_required, field_order) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (survey_id, 
                 field['field_type'], 
                 field['field_label'],
                 field_options,
                 field.get('is_required', False),
                 i + 1)
            )
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في حفظ الاستبيان: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_survey(survey_id: int, survey_name: str, is_active: bool, fields: List[Dict]) -> bool:
    """تحديث استبيان موجود"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. تحديث بيانات الاستبيان الأساسية
        cursor.execute(
            "UPDATE Surveys SET survey_name=%s, is_active=%s WHERE survey_id=%s",
            (survey_name, is_active, survey_id)
        )
        
        # 2. تحديث الحقول الموجودة أو إضافة جديدة
        for field in fields:
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            if 'field_id' in field:  # حقل موجود يتم تحديثه
                cursor.execute(
                    """UPDATE Survey_Fields 
                       SET field_label=%s, field_type=%s, field_options=%s, is_required=%s
                       WHERE field_id=%s""",
                    (field['field_label'], 
                     field['field_type'],
                     field_options,
                     field.get('is_required', False),
                     field['field_id'])
                )
            else:  # حقل جديد يتم إضافته
                cursor.execute("SELECT MAX(field_order) FROM Survey_Fields WHERE survey_id=%s", (survey_id,))
                max_order = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    """INSERT INTO Survey_Fields 
                       (survey_id, field_label, field_type, field_options, is_required, field_order) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (survey_id,
                     field['field_label'],
                     field['field_type'],
                     field_options,
                     field.get('is_required', False),
                     max_order + 1)
                )
        
        conn.commit()
        st.success("تم تحديث الاستبيان بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الاستبيان: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_survey(survey_id: int) -> bool:
    """حذف استبيان"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # حذف تفاصيل الإجابات المرتبطة
        cursor.execute('''
            DELETE FROM Response_Details 
            WHERE response_id IN (
                SELECT response_id FROM Responses WHERE survey_id = %s
            )
        ''', (survey_id,))
        
        # حذف الإجابات المرتبطة
        cursor.execute("DELETE FROM Responses WHERE survey_id = %s", (survey_id,))
        
        # حذف حقول الاستبيان
        cursor.execute("DELETE FROM Survey_Fields WHERE survey_id = %s", (survey_id,))
        
        # حذف الاستبيان نفسه
        cursor.execute("DELETE FROM Surveys WHERE survey_id = %s", (survey_id,))
        
        conn.commit()
        st.success("تم حذف الاستبيان بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء حذف الاستبيان: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_survey_fields(survey_id: int) -> List[Tuple]:
    """الحصول على حقول استبيان"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                field_id, 
                field_label, 
                field_type, 
                field_options, 
                is_required, 
                field_order
            FROM Survey_Fields
            WHERE survey_id = %s
            ORDER BY field_order
        ''', (survey_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب حقول الاستبيان: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

# دوال الإجابات
def save_response(survey_id: int, user_id: int, region_id: int, is_completed: bool = False) -> Optional[int]:
    """حفظ إجابة استبيان"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''INSERT INTO Responses 
               (survey_id, user_id, region_id, is_completed) 
               VALUES (%s, %s, %s, %s)
               RETURNING response_id''',
            (survey_id, user_id, region_id, is_completed)
        )
        response_id = cursor.fetchone()[0]
        conn.commit()
        return response_id
    except Exception as e:
        st.error(f"حدث خطأ في حفظ الاستجابة: {str(e)}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def save_response_detail(response_id: int, field_id: int, answer_value: str) -> bool:
    """حفظ تفاصيل الإجابة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO Response_Details (response_id, field_id, answer_value) VALUES (%s, %s, %s)",
            (response_id, field_id, str(answer_value) if answer_value is not None else "")
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_response_info(response_id: int) -> Optional[Tuple]:
    """الحصول على معلومات الإجابة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.response_id, s.survey_name, u.username, 
                   ha.admin_name, g.governorate_name, r.submission_date
            FROM Responses r
            JOIN Surveys s ON r.survey_id = s.survey_id
            JOIN Users u ON r.user_id = u.user_id
            JOIN HealthAdministrations ha ON r.region_id = ha.admin_id
            JOIN Governorates g ON ha.governorate_id = g.governorate_id
            WHERE r.response_id = %s
        ''', (response_id,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب معلومات الإجابة: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def get_response_details(response_id: int) -> List[Tuple]:
    """الحصول على تفاصيل الإجابة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rd.detail_id, rd.field_id, sf.field_label, 
                   sf.field_type, sf.field_options, rd.answer_value
            FROM Response_Details rd
            JOIN Survey_Fields sf ON rd.field_id = sf.field_id
            WHERE rd.response_id = %s
            ORDER BY sf.field_order
        ''', (response_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب تفاصيل الإجابة: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def update_response_detail(detail_id: int, new_value: str) -> bool:
    """تحديث تفاصيل الإجابة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Response_Details SET answer_value = %s WHERE detail_id = %s",
            (new_value, detail_id)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الإجابة: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def has_completed_survey_today(user_id: int, survey_id: int) -> bool:
    """التحقق من إكمال الاستبيان اليوم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM Responses 
            WHERE user_id = %s AND survey_id = %s AND is_completed = TRUE
            AND DATE(submission_date) = CURRENT_DATE
            LIMIT 1
        ''', (user_id, survey_id))
        return cursor.fetchone() is not None
    except Exception as e:
        st.error(f"حدث خطأ في التحقق من إكمال الاستبيان: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

# دوال الاستبيانات المسموح بها
def get_user_allowed_surveys(user_id: int) -> List[Tuple[int, str]]:
    """الحصول على الاستبيانات المسموح بها للمستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.survey_id, s.survey_name 
            FROM Surveys s
            JOIN UserSurveys us ON s.survey_id = us.survey_id
            WHERE us.user_id = %s
            ORDER BY s.survey_name
        ''', (user_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def update_user_allowed_surveys(user_id: int, survey_ids: List[int]) -> bool:
    """تحديث الاستبيانات المسموح بها للمستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # الحصول على محافظة المستخدم
        cursor.execute('''
            SELECT ha.governorate_id 
            FROM Users u
            JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
            WHERE u.user_id = %s
        ''', (user_id,))
        governorate_id = cursor.fetchone()
        
        if not governorate_id:
            st.error("المستخدم غير مرتبط بمحافظة")
            return False
        
        # التحقق من أن الاستبيانات مسموحة للمحافظة
        valid_surveys = []
        for survey_id in survey_ids:
            cursor.execute('''
                SELECT 1 FROM SurveyGovernorate 
                WHERE survey_id = %s AND governorate_id = %s
            ''', (survey_id, governorate_id[0]))
            if cursor.fetchone():
                valid_surveys.append(survey_id)
        
        # حذف جميع التصاريح الحالية
        cursor.execute("DELETE FROM UserSurveys WHERE user_id=%s", (user_id,))
        
        # إضافة التصاريح الجديدة
        for survey_id in valid_surveys:
            cursor.execute(
                "INSERT INTO UserSurveys (user_id, survey_id) VALUES (%s, %s)",
                (user_id, survey_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الاستبيانات المسموح بها: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# دوال سجل التعديلات
def log_audit_action(user_id: int, action_type: str, table_name: str, 
                    record_id: int = None, old_value: str = None, 
                    new_value: str = None) -> bool:
    """تسجيل إجراء في سجل التعديلات"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO AuditLog 
               (user_id, action_type, table_name, record_id, old_value, new_value)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, action_type, table_name, record_id, 
             json.dumps(old_value) if old_value else None,
             json.dumps(new_value) if new_value else None)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تسجيل الإجراء: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_audit_logs(
    table_name: str = None, 
    action_type: str = None,
    username: str = None,
    date_range: tuple = None,
    search_query: str = None
) -> List[Tuple]:
    """الحصول على سجل التعديلات مع فلاتر متقدمة"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = '''
            SELECT a.log_id, u.username, a.action_type, a.table_name, 
                   a.record_id, a.old_value, a.new_value, a.action_timestamp
            FROM AuditLog a
            JOIN Users u ON a.user_id = u.user_id
        '''
        params = []
        conditions = []
        
        # تطبيق الفلاتر
        if table_name:
            conditions.append("a.table_name = %s")
            params.append(table_name)
        if action_type:
            conditions.append("a.action_type = %s")
            params.append(action_type)
        if username:
            conditions.append("u.username LIKE %s")
            params.append(f"%{username}%")
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            conditions.append("DATE(a.action_timestamp) BETWEEN %s AND %s")
            params.extend([start_date, end_date])
        if search_query:
            conditions.append("""
                (a.old_value LIKE %s OR 
                 a.new_value LIKE %s OR 
                 u.username LIKE %s OR 
                 a.table_name LIKE %s OR
                 a.action_type LIKE %s)
            """)
            search_term = f"%{search_query}%"
            params.extend([search_term, search_term, search_term, search_term, search_term])
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
            
        query += ' ORDER BY a.action_timestamp DESC'
        
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب سجل التعديلات: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()