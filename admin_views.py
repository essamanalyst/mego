import streamlit as st
import psycopg2
from database import (
    get_db_connection,
    get_all_users_for_admin_view,
    get_audit_logs,
    get_response_info,
    get_response_details,
    update_response_detail,
    get_user_by_username,
    update_user_allowed_surveys,
    add_governorate_admin,
    get_health_admins,
    update_user,
    update_survey,
    get_governorates_list,
    add_user,
    save_survey,
    delete_survey
)
import json
import pandas as pd
from datetime import datetime

def show_admin_dashboard():
    st.title("لوحة تحكم النظام")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "إدارة المستخدمين",
        "إدارة المحافظات",
        "إدارة الإدارات الصحية",
        "إدارة الاستبيانات",
        "عرض البيانات"
    ])

    with tab1:
        manage_users()
    with tab2:
        manage_governorates()
    with tab3:
        manage_regions()
    with tab4:
        manage_surveys()
    with tab5:
        view_data()

def manage_users():
    st.header("إدارة المستخدمين")
    
    # عرض المستخدمين الحاليين
    users = get_all_users_for_admin_view()
    
    # عرض جدول المستخدمين
    for user in users:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
        with col1:
            st.write(user[1])
        with col2:
            role = "مسؤول نظام" if user[2] == "admin" else "مسؤول محافظة" if user[2] == "governorate_admin" else "موظف"
            st.write(role)
        with col3:
            st.write(user[3] if user[3] else "غير محدد")
        with col4:
            st.write(user[4] if user[4] else "غير محدد")
        with col5:
            if st.button("تعديل", key=f"edit_{user[0]}"):
                st.session_state.editing_user = user[0]
        with col6:
            if st.button("حذف", key=f"delete_{user[0]}"):
                delete_user(user[0])
                st.rerun()
    
    if 'editing_user' in st.session_state:
        edit_user_form(st.session_state.editing_user)
    
    with st.expander("إضافة مستخدم جديد"):
        add_user_form()

def add_user_form():
    governorates = get_governorates_list()
    # استبدال استدعاء Supabase المباشر
    conn = database.get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT survey_id, survey_name FROM Surveys;")
            surveys = cur.fetchall()
        conn.close()
    else:
        surveys = []

    if 'add_user_form_data' not in st.session_state:
        st.session_state.add_user_form_data = {
            'username': '',
            'password': '',
            'role': 'employee',
            'governorate_id': None,
            'admin_id': None,
            'allowed_surveys': []
        }

    form = st.form(key="add_user_form", clear_on_submit=True)

    with form:
        st.subheader("المعلومات الأساسية")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("اسم المستخدم*",
                                   value=st.session_state.add_user_form_data['username'],
                                   key="new_user_username")
        with col2:
            password = st.text_input("كلمة المرور*",
                                   type="password",
                                   value=st.session_state.add_user_form_data['password'],
                                   key="new_user_password")

        role = st.selectbox("الدور*",
                          ["admin", "governorate_admin", "employee"],
                          index=["admin", "governorate_admin", "employee"].index(
                              st.session_state.add_user_form_data['role']),
                          key="new_user_role")

        selected_gov = None
        selected_admin = None

        if role == "governorate_admin":
            st.subheader("بيانات مسؤول المحافظة")
            if governorates:
                # تحويل قائمة التوابل إلى قائمة قواميس لتسهيل الوصول
                gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=list(gov_options_dict.keys()),
                    index=list(gov_options_dict.keys()).index(
                        st.session_state.add_user_form_data['governorate_id'])
                        if st.session_state.add_user_form_data['governorate_id'] in gov_options_dict else 0,
                    format_func=lambda x: gov_options_dict[x],
                    key="gov_admin_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        elif role == "employee":
            st.subheader("بيانات الموظف")
            if governorates:
                gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=list(gov_options_dict.keys()),
                    index=list(gov_options_dict.keys()).index(
                        st.session_state.add_user_form_data['governorate_id'])
                        if st.session_state.add_user_form_data['governorate_id'] in gov_options_dict else 0,
                    format_func=lambda x: gov_options_dict[x],
                    key="employee_gov_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov

                # استبدال استدعاء Supabase المباشر
                conn = database.get_db_connection()
                if conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute("SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id = %s;", (selected_gov,))
                        health_admins = cur.fetchall()
                    conn.close()
                else:
                    health_admins = []

                if health_admins:
                    admin_options_dict = {a['admin_id']: a['admin_name'] for a in health_admins}
                    selected_admin = st.selectbox(
                        "الإدارة الصحية*",
                        options=list(admin_options_dict.keys()),
                        index=list(admin_options_dict.keys()).index(
                            st.session_state.add_user_form_data['admin_id'])
                            if st.session_state.add_user_form_data['admin_id'] in admin_options_dict else 0,
                        format_func=lambda x: admin_options_dict[x],
                        key="employee_admin_select")
                    st.session_state.add_user_form_data['admin_id'] = selected_admin
                else:
                    st.warning("لا توجد إدارات صحية في هذه المحافظة. يرجى إضافتها أولاً.")
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        if role != "admin" and surveys:
            survey_options_dict = {s['survey_id']: s['survey_name'] for s in surveys}
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=list(survey_options_dict.keys()),
                default=st.session_state.add_user_form_data['allowed_surveys'],
                format_func=lambda x: survey_options_dict[x],
                key="allowed_surveys_select")
            st.session_state.add_user_form_data['allowed_surveys'] = selected_surveys

        col1, col2 = st.columns([3, 1])
        with col1:
            submit_button = st.form_submit_button("💾 حفظ المستخدم")
        with col2:
            clear_button = st.form_submit_button("🧹 تنظيف الحقول")

        if submit_button:
            if not username or not password:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                return

            if role == "governorate_admin" and not selected_gov:
                st.error("يرجى اختيار محافظة لمسؤول المحافظة")
                return

            if role == "employee" and not selected_admin:
                st.error("يرجى اختيار إدارة صحية للموظف")
                return

            if add_user(username, password, role, selected_admin if role == "employee" else None):
                user = get_user_by_username(username)
                if user:
                    if role == "governorate_admin":
                        add_governorate_admin(user['user_id'], selected_gov)

                    if role != "admin" and selected_surveys:
                        update_user_allowed_surveys(user['user_id'], selected_surveys)

                    st.success(f"تمت إضافة المستخدم {username} بنجاح")
                    st.session_state.add_user_form_data = {
                        'username': '',
                        'password': '',
                        'role': 'employee',
                        'governorate_id': None,
                        'admin_id': None,
                        'allowed_surveys': []
                    }
                    st.rerun()

        if clear_button:
            st.session_state.add_user_form_data = {
                'username': '',
                'password': '',
                'role': 'employee',
                'governorate_id': None,
                'admin_id': None,
                'allowed_surveys': []
            }
            st.rerun()

def edit_user_form(user_id):
    user = get_user_by_username(user_id) # استخدام الدالة الجديدة
    if not user:
        st.error("المستخدم غير موجود!")
        del st.session_state.editing_user
        return

    governorates = get_governorates_list()
    # استبدال استدعاء Supabase المباشر
    conn = database.get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT survey_id, survey_name FROM Surveys;")
            surveys = cur.fetchall()
        conn.close()
    else:
        surveys = []

    allowed_surveys_data = get_user_allowed_surveys(user_id)
    allowed_surveys = [s[0] for s in allowed_surveys_data]

    current_gov = None
    current_admin = user.get('assigned_region')

    if user['role'] == 'governorate_admin':
        # استبدال استدعاء Supabase المباشر
        conn = database.get_db_connection()
        if conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT governorate_id FROM GovernorateAdmins WHERE user_id = %s;", (user_id,))
                gov_admin = cur.fetchone()
            conn.close()
        else:
            gov_admin = None
        if gov_admin:
            current_gov = gov_admin['governorate_id']
    elif user['role'] == 'employee' and user.get('assigned_region'):
        # إذا كان موظفاً، فالمحافظة مرتبطة بالإدارة الصحية
        conn = database.get_db_connection()
        if conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT governorate_id FROM HealthAdministrations WHERE admin_id = %s;", (user['assigned_region'],))
                health_admin_gov = cur.fetchone()
            conn.close()
        else:
            health_admin_gov = None
        if health_admin_gov:
            current_gov = health_admin_gov['governorate_id']


    with st.form(f"edit_user_{user_id}"):
        new_username = st.text_input("اسم المستخدم", value=user['username'])
        new_role = st.selectbox(
            "الدور",
            ["admin", "governorate_admin", "employee"],
            index=["admin", "governorate_admin", "employee"].index(user['role'])
        )

        selected_gov = current_gov
        selected_admin = current_admin

        if governorates:
            gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}
            gov_options_keys = list(gov_options_dict.keys())
            if current_gov in gov_options_keys:
                gov_index = gov_options_keys.index(current_gov)
            else:
                gov_index = 0 # أو اختر قيمة افتراضية أخرى

            if new_role == "governorate_admin":
                selected_gov = st.selectbox(
                    "المحافظة",
                    options=gov_options_keys,
                    index=gov_index,
                    format_func=lambda x: gov_options_dict[x],
                    key=f"gov_edit_{user_id}"
                )
            elif new_role == "employee":
                selected_gov = st.selectbox(
                    "المحافظة",
                    options=gov_options_keys,
                    index=gov_index,
                    format_func=lambda x: gov_options_dict[x],
                    key=f"emp_gov_{user_id}"
                )

                # استبدال استدعاء Supabase المباشر
                conn = database.get_db_connection()
                if conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute("SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id = %s;", (selected_gov,))
                        health_admins = cur.fetchall()
                    conn.close()
                else:
                    health_admins = []

                if health_admins:
                    admin_options = [a['admin_id'] for a in health_admins]
                    admin_options_dict = {a['admin_id']: a['admin_name'] for a in health_admins}
                    try:
                        admin_index = admin_options.index(current_admin) if current_admin in admin_options else 0
                    except ValueError:
                        admin_index = 0

                    selected_admin = st.selectbox(
                        "الإدارة الصحية",
                        options=admin_options,
                        index=admin_index,
                        format_func=lambda x: admin_options_dict[x],
                        key=f"admin_edit_{user_id}"
                    )
                else:
                    st.warning("لا توجد إدارات صحية في هذه المحافظة.")
                    selected_admin = None # لا توجد إدارة صحية للاختيار

        if new_role != "admin" and surveys:
            survey_options_dict = {s['survey_id']: s['survey_name'] for s in surveys}
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=list(survey_options_dict.keys()),
                default=[s for s in allowed_surveys if s in survey_options_dict],
                format_func=lambda x: survey_options_dict[x],
                key=f"surveys_edit_{user_id}"
            )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if new_role == "governorate_admin":
                    update_user(user_id, new_username, new_role)
                    # حذف وإضافة مسؤول المحافظة
                    conn = database.get_db_connection()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM GovernorateAdmins WHERE user_id = %s;", (user_id,))
                            cur.execute("INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (%s, %s);", (user_id, selected_gov))
                        conn.commit()
                        conn.close()
                    else:
                        st.error("خطأ في الاتصال بقاعدة البيانات.")
                        return

                    if new_role != "admin":
                        update_user_allowed_surveys(user_id, selected_surveys)
                else:
                    update_user(user_id, new_username, new_role, selected_admin if new_role == "employee" else None)
                    # إذا تغير الدور من governorate_admin إلى شيء آخر، احذف من GovernorateAdmins
                    if user['role'] == 'governorate_admin' and new_role != 'governorate_admin':
                        conn = database.get_db_connection()
                        if conn:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM GovernorateAdmins WHERE user_id = %s;", (user_id,))
                            conn.commit()
                            conn.close()
                    if new_role != "admin":
                        update_user_allowed_surveys(user_id, selected_surveys)

                del st.session_state.editing_user
                st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_user
                st.rerun()

def delete_user(user_id):
    try:
        # استبدال استدعاء Supabase المباشر
        conn = database.get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT response_id FROM Responses WHERE user_id = %s LIMIT 1;", (user_id,))
                has_responses = cur.fetchone()
            conn.close()
        else:
            st.error("خطأ في الاتصال بقاعدة البيانات.")
            return False

        if has_responses:
            st.error("لا يمكن حذف المستخدم لأنه لديه إجابات مسجلة!")
            return False

        # حذف من UserSurveys أولاً
        conn = database.get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM UserSurveys WHERE user_id = %s;", (user_id,))
            conn.commit()
            conn.close()

        # حذف من GovernorateAdmins إذا كان مسؤول محافظة
        conn = database.get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM GovernorateAdmins WHERE user_id = %s;", (user_id,))
            conn.commit()
            conn.close()

        # حذف المستخدم نفسه
        conn = database.get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Users WHERE user_id = %s;", (user_id,))
            conn.commit()
            conn.close()
        else:
            st.error("خطأ في الاتصال بقاعدة البيانات.")
            return False

        st.success("تم حذف المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False

def manage_surveys():
    st.header("إدارة الاستبيانات")

    # استبدال استدعاء Supabase المباشر
    conn = database.get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT survey_id, survey_name, created_at, is_active FROM Surveys ORDER BY created_at DESC;")
            surveys = cur.fetchall()
        conn.close()
    else:
        surveys = []

    if surveys:
        for survey in surveys:
            col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
            with col1:
                st.write(f"**{survey['survey_name']}** (تم الإنشاء في {survey['created_at'].strftime('%Y-%m-%d')})")
            with col2:
                status = "نشط" if survey['is_active'] else "غير نشط"
                st.write(f"الحالة: {status}")
            with col3:
                if st.button("تعديل", key=f"edit_survey_{survey['survey_id']}"):
                    st.session_state.editing_survey = survey['survey_id']
            with col4:
                if st.button("حذف", key=f"delete_survey_{survey['survey_id']}"):
                    delete_survey(survey['survey_id'])
                    st.rerun()
    else:
        st.info("لا توجد استبيانات لعرضها.")

    if 'editing_survey' in st.session_state:
        edit_survey(st.session_state.editing_survey)

    with st.expander("إنشاء استبيان جديد"):
        create_survey_form()

def edit_survey(survey_id):
    survey = get_survey_by_id(survey_id) # استخدام الدالة الجديدة
    if not survey:
        st.error("الاستبيان غير موجود!")
        del st.session_state.editing_survey
        return

    fields = get_survey_fields(survey_id) # استخدام الدالة الجديدة

    if 'new_survey_fields' not in st.session_state:
        st.session_state.new_survey_fields = []

    with st.form(f"edit_survey_{survey_id}"):
        st.subheader("تعديل الاستبيان")
        new_name = st.text_input("اسم الاستبيان", value=survey['survey_name'])
        is_active = st.checkbox("نشط", value=bool(survey['is_active']))

        st.subheader("الحقول الحالية")
        updated_fields = []
        for field in fields:
            with st.expander(f"حقل: {field[1]} (نوع: {field[2]})"): # field[1] for label, field[2] for type
                col1, col2 = st.columns(2)
                with col1:
                    new_label = st.text_input("تسمية الحقل", value=field[1], key=f"label_{field[0]}") # field[0] for field_id
                    new_type = st.selectbox(
                        "نوع الحقل",
                        ["text", "number", "dropdown", "checkbox", "date"],
                        index=["text", "number", "dropdown", "checkbox", "date"].index(field[2]), # field[2] for type
                        key=f"type_{field[0]}"
                    )
                with col2:
                    new_required = st.checkbox("مطلوب", value=bool(field[4]), key=f"required_{field[0]}") # field[4] for is_required
                    if new_type == 'dropdown':
                        options = "\n".join(json.loads(field[3])) if field[3] else "" # field[3] for options
                        new_options = st.text_area(
                            "خيارات القائمة المنسدلة (سطر لكل خيار)",
                            value=options,
                            key=f"options_{field[0]}"
                        )
                    else:
                        new_options = None

                updated_fields.append({
                    'field_id': field[0],
                    'field_label': new_label,
                    'field_type': new_type,
                    'field_options': [opt.strip() for opt in new_options.split('\n')] if new_options else None,
                    'is_required': new_required
                })

        st.subheader("إضافة حقول جديدة")
        for i, field in enumerate(st.session_state.new_survey_fields):
            st.markdown(f"#### الحقل الجديد {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل",
                                                   value=field.get('field_label', ''),
                                                   key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب",
                                                 value=field.get('is_required', False),
                                                 key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("➕ إضافة حقل جديد"):
                st.session_state.new_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
                st.rerun()
        with col2:
            if st.form_submit_button("🗑️ حذف آخر حقل") and st.session_state.new_survey_fields:
                st.session_state.new_survey_fields.pop()
                st.rerun()

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 حفظ التعديلات"):
                all_fields = updated_fields + st.session_state.new_survey_fields
                if update_survey(survey_id, new_name, is_active, all_fields):
                    st.success("تم تحديث الاستبيان بنجاح")
                    st.session_state.new_survey_fields = []
                    del st.session_state.editing_survey
                    st.rerun()
        with col2:
            if st.form_submit_button("❌ إلغاء"):
                st.session_state.new_survey_fields = []
                del st.session_state.editing_survey
                st.rerun()

def create_survey_form():
    if 'create_survey_fields' not in st.session_state:
        st.session_state.create_survey_fields = []

    governorates = get_governorates_list()
    gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}

    with st.form("create_survey_form"):
        survey_name = st.text_input("اسم الاستبيان")

        selected_governorates = st.multiselect(
            "المحافظات المسموحة",
            options=list(gov_options_dict.keys()),
            format_func=lambda x: gov_options_dict[x]
        )

        st.subheader("حقول الاستبيان")

        for i, field in enumerate(st.session_state.create_survey_fields):
            st.subheader(f"الحقل {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", value=field.get('field_label', ''), key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", value=field.get('is_required', False), key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("إضافة حقل جديد"):
                st.session_state.create_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
        with col2:
            if st.form_submit_button("حذف آخر حقل") and st.session_state.create_survey_fields:
                st.session_state.create_survey_fields.pop()
        with col3:
            if st.form_submit_button("حفظ الاستبيان") and survey_name:
                save_survey(survey_name, st.session_state.create_survey_fields, selected_governorates)
                st.session_state.create_survey_fields = []
                st.rerun()

def display_survey_data(survey_id):
    survey = get_survey_by_id(survey_id) # استخدام الدالة الجديدة
    if not survey:
        st.error("الاستبيان المحدد غير موجود")
        return

    survey_name = survey['survey_name']
    st.subheader(f"بيانات الاستبيان: {survey_name}")

    responses = get_responses_for_survey(survey_id) # استخدام الدالة الجديدة
    total_responses = len(responses)

    if total_responses == 0:
        st.info("لا توجد بيانات متاحة لهذا الاستبيان بعد")
        return

    completed_responses = sum(1 for r in responses if r['is_completed'])
    regions_count = len(set(r['admin_name'] for r in responses))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("إجمالي الإجابات", total_responses)
    with col2:
        st.metric("الإجابات المكتملة", completed_responses)
    with col3:
        st.metric("عدد المناطق", regions_count)

    df = pd.DataFrame(
        [(r['response_id'], r['username'],
          r['admin_name'],
          r['governorate_name'],
          r['submission_date'],
          "مكتملة" if r['is_completed'] else "مسودة") for r in responses],
        columns=["ID", "المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
    )

    st.dataframe(df)

    if st.button("تصدير شامل لجميع البيانات إلى Excel", key=f"export_excel_{survey_id}"):
        import re
        from io import BytesIO

        filename = re.sub(r'[^\w\-_]', '_', survey_name) + "_كامل_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='ملخص_الإجابات', index=False)

            all_details = []
            for response in responses:
                details = get_response_details(response['response_id']) # استخدام الدالة الجديدة

                for detail in details:
                    # تفاصيل الإجابة تأتي الآن كـ (detail_id, field_id, label, field_type, options, answer)
                    # نحتاج لجلب معلومات المستخدم وتاريخ الإدخال من استجابة الـ `responses` الأصلية
                    all_details.append({
                        "ID الإجابة": response['response_id'],
                        "الحقل": detail[2], # label
                        "القيمة": detail[5], # answer
                        "أدخلها": response['username'],
                        "تاريخ الإدخال": response['submission_date'],
                        "حالة الإجابة": "مكتملة" if response['is_completed'] else "مسودة"
                    })

            if all_details:
                details_df = pd.DataFrame(all_details)
                details_df.to_excel(writer, sheet_name='تفاصيل_الإجابات', index=False)

            fields = get_survey_fields(survey_id) # استخدام الدالة الجديدة
            fields_df = pd.DataFrame(
                [(f[1], f[2], json.loads(f[3]) if f[3] else None, "نعم" if f[4] else "لا") for f in fields],
                columns=["اسم الحقل", "نوع الحقل", "الخيارات", "مطلوب"]
            )
            fields_df.to_excel(writer, sheet_name='حقول_الاستبيان', index=False)

            users_df = pd.DataFrame(
                [(r['username'], r['admin_name'],
                 r['governorate_name'],
                 r['submission_date'], "مكتملة" if r['is_completed'] else "مسودة") for r in responses],
                columns=["المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
            )
            users_df.drop_duplicates().to_excel(writer, sheet_name='المستخدمين', index=False)

        with open(filename, "rb") as f:
            st.download_button(
                label="تنزيل ملف Excel الكامل",
                data=f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download_excel_{survey_id}"
            )
        st.success("تم إنشاء ملف Excel الشامل بنجاح")

    selected_response_id = st.selectbox(
        "اختر إجابة لعرض وتعديل تفاصيلها",
        options=[r['response_id'] for r in responses],
        format_func=lambda x: f"إجابة #{x}",
        key=f"select_response_{survey_id}"
    )

    if selected_response_id:
        response_info = get_response_info(selected_response_id)
        if response_info:
            st.subheader(f"تفاصيل الإجابة #{selected_response_id}")
            st.markdown(f"""
            **الاستبيان:** {response_info[1]}
            **المستخدم:** {response_info[2]}
            **الإدارة الصحية:** {response_info[3]}
            **المحافظة:** {response_info[4]}
            **تاريخ التقديم:** {response_info[5]}
            """)

            details = get_response_details(selected_response_id)
            updates = {}

            with st.form(key=f"edit_response_form_{selected_response_id}"):
                for detail in details:
                    detail_id, field_id, label, field_type, options, answer = detail

                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"**{label}**")
                    with col2:
                        if field_type == 'dropdown':
                            options_list = json.loads(options) if options else []
                            new_value = st.selectbox(
                                label,
                                options_list,
                                index=options_list.index(answer) if answer in options_list else 0,
                                key=f"dropdown_{detail_id}_{selected_response_id}"
                            )
                        else:
                            new_value = st.text_input(
                                label,
                                value=answer,
                                key=f"input_{detail_id}_{selected_response_id}"
                            )

                        if new_value != answer:
                            updates[detail_id] = new_value

                col1, col2 = st.columns(2)
                with col1:
                    save_clicked = st.form_submit_button("💾 حفظ جميع التعديلات")
                    if save_clicked:
                        if updates:
                            success_count = 0
                            for detail_id, new_value in updates.items():
                                if update_response_detail(detail_id, new_value):
                                    success_count += 1

                            if success_count == len(updates):
                                st.success("تم تحديث جميع التعديلات بنجاح")
                            else:
                                st.error(f"تم تحديث {success_count} من أصل {len(updates)} تعديلات")
                            st.rerun()
                        else:
                            st.info("لم تقم بإجراء أي تعديلات")
                with col2:
                    cancel_clicked = st.form_submit_button("❌ إلغاء التعديلات")
                    if cancel_clicked:
                        st.rerun()

def view_data():
    st.header("عرض البيانات المجمعة")

    # استبدال استدعاء Supabase المباشر
    conn = database.get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT survey_id, survey_name FROM Surveys ORDER BY survey_name;")
            surveys = cur.fetchall()
        conn.close()
    else:
        surveys = []

    if not surveys:
        st.warning("لا توجد استبيانات متاحة")
        return

    selected_survey = st.selectbox(
        "اختر استبيان",
        surveys,
        format_func=lambda x: x['survey_name'],
        key="survey_select"
    )

    if selected_survey:
        display_survey_data(selected_survey['survey_id'])

def manage_governorates():
    st.header("إدارة المحافظات")
    governorates = get_governorates_list() # استخدام الدالة الجديدة

    if governorates:
        for gov in governorates:
            col1, col2, col3, col4 = st.columns([4, 3, 1, 1])
            with col1:
                st.write(f"**{gov['governorate_name']}**")
            with col2:
                st.write(gov['description'] if gov['description'] else "لا يوجد وصف")
            with col3:
                if st.button("تعديل", key=f"edit_gov_{gov['governorate_id']}"):
                    st.session_state.editing_gov = gov['governorate_id']
            with col4:
                if st.button("حذف", key=f"delete_gov_{gov['governorate_id']}"):
                    delete_governorate(gov['governorate_id']) # استخدام الدالة الجديدة
                    st.rerun()
    else:
        st.info("لا توجد محافظات لعرضها.")

    if 'editing_gov' in st.session_state:
        edit_governorate(st.session_state.editing_gov)

    with st.expander("إضافة محافظة جديدة"):
        with st.form("add_governorate_form"):
            governorate_name = st.text_input("اسم المحافظة")
            description = st.text_area("الوصف")

            submitted = st.form_submit_button("حفظ")

            if submitted:
                if governorate_name:
                    # التحقق من وجود المحافظة
                    conn = database.get_db_connection()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT governorate_id FROM Governorates WHERE governorate_name = %s;", (governorate_name,))
                            existing = cur.fetchone()
                        conn.close()
                    else:
                        st.error("خطأ في الاتصال بقاعدة البيانات.")
                        return

                    if existing:
                        st.error("هذه المحافظة موجودة بالفعل!")
                    else:
                        if add_governorate(governorate_name, description): # استخدام الدالة الجديدة
                            st.success("تمت إضافة المحافظة بنجاح")
                            st.rerun()
                else:
                    st.warning("يرجى إدخال اسم المحافظة")

def edit_governorate(gov_id):
    gov = get_governorate_by_id(gov_id) # استخدام الدالة الجديدة
    if not gov:
        st.error("المحافظة غير موجودة")
        del st.session_state.editing_gov
        return

    with st.form(f"edit_gov_{gov_id}"):
        new_name = st.text_input("اسم المحافظة", value=gov['governorate_name'])
        new_desc = st.text_area("الوصف", value=gov['description'] if gov['description'] else "")

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                # التحقق من وجود الاسم الجديد لمحافظة أخرى
                conn = database.get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT governorate_id FROM Governorates WHERE governorate_name = %s AND governorate_id != %s;", (new_name, gov_id))
                        existing = cur.fetchone()
                    conn.close()
                else:
                    st.error("خطأ في الاتصال بقاعدة البيانات.")
                    return

                if existing:
                    st.error("هذا الاسم مستخدم بالفعل لمحافظة أخرى!")
                else:
                    if update_governorate(gov_id, new_name, new_desc): # استخدام الدالة الجديدة
                        st.success("تم تحديث المحافظة بنجاح")
                        del st.session_state.editing_gov
                        st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_gov
                st.rerun()

def manage_regions():
    st.header("إدارة الإدارات الصحية")

    # استبدال استدعاء Supabase المباشر
    conn = database.get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ha.admin_id,
                    ha.admin_name,
                    ha.description,
                    g.governorate_name
                FROM
                    HealthAdministrations ha
                JOIN
                    Governorates g ON ha.governorate_id = g.governorate_id
                ORDER BY g.governorate_name, ha.admin_name;
            """)
            regions = cur.fetchall()
        conn.close()
    else:
        regions = []

    if regions:
        for reg in regions:
            col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
            with col1:
                st.write(f"**{reg['admin_name']}**")
            with col2:
                st.write(reg['description'] if reg['description'] else "لا يوجد وصف")
            with col3:
                st.write(reg['governorate_name'])
            with col4:
                if st.button("تعديل", key=f"edit_reg_{reg['admin_id']}"):
                    st.session_state.editing_reg = reg['admin_id']
            with col5:
                if st.button("حذف", key=f"delete_reg_{reg['admin_id']}"):
                    delete_health_admin(reg['admin_id']) # استخدام الدالة الجديدة
                    st.rerun()
    else:
        st.info("لا توجد إدارات صحية لعرضها.")

    if 'editing_reg' in st.session_state:
        edit_health_admin(st.session_state.editing_reg)

    with st.expander("إضافة إدارة صحية جديدة"):
        governorates = get_governorates_list()
        gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}

        if not governorates:
            st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")
            return

        with st.form("add_health_admin_form"):
            admin_name = st.text_input("اسم الإدارة الصحية")
            description = st.text_area("الوصف")
            governorate_id = st.selectbox(
                "المحافظة",
                options=list(gov_options_dict.keys()),
                format_func=lambda x: gov_options_dict[x])

            submitted = st.form_submit_button("حفظ")

            if submitted:
                if admin_name:
                    # التحقق من التكرار
                    conn = database.get_db_connection()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT admin_id FROM HealthAdministrations WHERE admin_name = %s AND governorate_id = %s;", (admin_name, governorate_id))
                            existing = cur.fetchone()
                        conn.close()
                    else:
                        st.error("خطأ في الاتصال بقاعدة البيانات.")
                        return

                    if existing:
                        st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
                    else:
                        if add_health_admin(admin_name, description, governorate_id): # استخدام الدالة الجديدة
                            st.success("تمت إضافة الإدارة الصحية بنجاح")
                            st.rerun()
                else:
                    st.warning("يرجى إدخال اسم الإدارة الصحية")

def edit_health_admin(admin_id):
    admin = get_health_admin_by_id(admin_id) # استخدام الدالة الجديدة

    if not admin:
        st.error("الإدارة الصحية المطلوبة غير موجودة!")
        del st.session_state.editing_reg
        return

    governorates = get_governorates_list()
    gov_options_dict = {g['governorate_id']: g['governorate_name'] for g in governorates}

    with st.form(f"edit_admin_{admin_id}"):
        new_name = st.text_input("اسم الإدارة الصحية", value=admin['admin_name'])
        new_desc = st.text_area("الوصف", value=admin['description'] if admin['description'] else "")
        new_gov = st.selectbox(
            "المحافظة",
            options=list(gov_options_dict.keys()),
            index=list(gov_options_dict.keys()).index(admin['governorate_id']),
            format_func=lambda x: gov_options_dict[x])

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                # التحقق من التكرار
                conn = database.get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT admin_id FROM HealthAdministrations WHERE admin_name = %s AND governorate_id = %s AND admin_id != %s;", (new_name, new_gov, admin_id))
                        existing = cur.fetchone()
                    conn.close()
                else:
                    st.error("خطأ في الاتصال بقاعدة البيانات.")
                    return

                if existing:
                    st.error("هذا الاسم مستخدم بالفعل لإدارة صحية أخرى في هذه المحافظة!")
                else:
                    if update_health_admin(admin_id, new_name, new_desc, new_gov): # استخدام الدالة الجديدة
                        st.success("تم تحديث الإدارة الصحية بنجاح")
                        del st.session_state.editing_reg
                        st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_reg
                st.rerun()

def export_to_excel(data):
    from io import BytesIO
    import time

    df = pd.DataFrame(
        [(log[0], log[1], log[2], log[3],
         log[4], log[5], log[6], log[7]) for log in data],
        columns=["ID", "المستخدم", "الإجراء", "الجدول", "رقم السجل",
                 "القيمة القديمة", "القيمة الجديدة", "الوقت"]
    )

    output = BytesIO()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"audit_logs_export_{timestamp}.xlsx"

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='سجل التعديلات')
        summary = df.groupby(['الجدول', 'الإجراء']).size().unstack(fill_value=0)
        summary.to_excel(writer, sheet_name='ملخص الإجراءات')

    st.download_button(
        label="⬇️ تنزيل ملف Excel",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("تم إنشاء ملف التصدير بنجاح")

def export_to_csv(data):
    import time

    df = pd.DataFrame(
        [(log[0], log[1], log[2], log[3],
         log[4], log[5], log[6], log[7]) for log in data],
        columns=["ID", "المستخدم", "الإجراء", "الجدول", "رقم السجل",
                 "القيمة القديمة", "القيمة الجديدة", "الوقت"]
    )

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"audit_logs_export_{timestamp}.csv"

    st.download_button(
        label="⬇️ تنزيل ملف CSV",
        data=df.to_csv(index=False, encoding='utf-8-sig'),
        file_name=filename,
        mime="text/csv"
    )

    st.success("تم إنشاء ملف التصدير بنجاح")

