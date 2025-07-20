import streamlit as st
import pandas as pd
from datetime import datetime
import json
from database import (
    get_health_admin_name,
    save_response,
    save_response_detail,
    get_survey_fields,
    has_completed_survey_today,
    get_allowed_surveys, # إضافة هذه الدالة
    get_user_by_username, # لاستخدامها في get_last_login
    get_survey_by_id, # لاستخدامها في display_single_survey
    get_response_details # لاستخدامها في view_survey_responses
)
import database # استيراد الوحدة بأكملها للوصول إلى get_db_connection
import psycopg2
def show_employee_dashboard():
    if not st.session_state.get('region_id'):
        st.error("حسابك غير مرتبط بأي منطقة. يرجى التواصل مع المسؤول.")
        return

    region_info = get_employee_region_info(st.session_state.region_id)
    if not region_info:
        st.error("لم يتم العثور على معلومات المنطقة الخاصة بك في النظام")
        return

    display_employee_header(region_info)
    allowed_surveys = get_allowed_surveys(st.session_state.user_id)

    if not allowed_surveys:
        st.info("لا توجد استبيانات متاحة لك حاليًا")
        return

    selected_surveys = display_survey_selection(allowed_surveys)

    for survey_item in selected_surveys: # selected_surveys الآن هي قائمة قواميس
        display_single_survey(survey_item['survey_id'], region_info['admin_id'])

def get_employee_region_info(region_id):
    try:
        # استبدال استدعاء Supabase المباشر
        conn = database.get_db_connection()
        if conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        ha.admin_id,
                        ha.admin_name,
                        g.governorate_name,
                        g.governorate_id
                    FROM
                        HealthAdministrations ha
                    JOIN
                        Governorates g ON ha.governorate_id = g.governorate_id
                    WHERE
                        ha.admin_id = %s;
                """, (region_id,))
                result = cur.fetchone()
            conn.close()
        else:
            return None

        if result:
            return {
                'admin_id': result['admin_id'],
                'admin_name': result['admin_name'],
                'governorate_name': result['governorate_name'],
                'governorate_id': result['governorate_id']
            }
        return None
    except Exception as e:
        st.error(f"خطأ في قاعدة البيانات: {str(e)}")
        return None

def display_employee_header(region_info):
    st.set_page_config(layout="wide")
    st.title(f"لوحة الموظف - {region_info['admin_name']}")

    last_login = get_last_login(st.session_state.user_id)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("المحافظة")
        st.info(region_info['governorate_name'])
    with col2:
        st.subheader("الإدارة الصحية")
        st.info(region_info['admin_name'])
    with col3:
        st.subheader("آخر دخول")
        st.info(last_login if last_login else "غير معروف")

def get_last_login(user_id):
    user_data = get_user_by_username(user_id) # استخدام الدالة الجديدة
    return user_data['last_login'] if user_data and user_data.get('last_login') else None

def display_survey_selection(allowed_surveys):
    st.header("الاستبيانات المتاحة")

    # allowed_surveys هي الآن قائمة قواميس {survey_id, survey_name}
    selected_survey_ids = st.multiselect(
        "اختر استبيان أو أكثر",
        options=[s['survey_id'] for s in allowed_surveys],
        format_func=lambda x: next(s['survey_name'] for s in allowed_surveys if s['survey_id'] == x),
        key="selected_surveys"
    )
    # إرجاع القواميس الكاملة للاستبيانات المختارة
    return [s for s in allowed_surveys if s['survey_id'] in selected_survey_ids]

def display_single_survey(survey_id, region_id):
    try:
        survey_info = get_survey_by_id(survey_id) # استخدام الدالة الجديدة

        if not survey_info:
            st.error("الاستبيان المحدد غير موجود")
            return

        if has_completed_survey_today(st.session_state.user_id, survey_id):
            st.warning(f"لقد أكملت استبيان '{survey_info['survey_name']}' اليوم. يمكنك إكماله مرة أخرى غدًا.")
            return

        with st.expander(f"📋 {survey_info['survey_name']} (تاريخ الإنشاء: {survey_info['created_at'].strftime('%Y-%m-%d')})"):
            fields = get_survey_fields(survey_id)
            display_survey_form(survey_id, region_id, fields, survey_info['survey_name'])

    except Exception as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")

def display_survey_form(survey_id, region_id, fields, survey_name):
    with st.form(f"survey_form_{survey_id}"):
        st.markdown("**يرجى تعبئة جميع الحقول المطلوبة (*)**")
        st.subheader("🧾 بيانات الاستبيان")

        answers = {}
        for field in fields:
            field_id, label, field_type, options, is_required, _ = field
            answers[field_id] = render_field(field_id, label, field_type, options, is_required)

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("🚀 إرسال النموذج")
        with col2:
            save_draft = st.form_submit_button("💾 حفظ مسودة")

        if submitted or save_draft:
            process_survey_submission(
                survey_id,
                region_id,
                fields,
                answers,
                submitted,
                survey_name
            )

def render_field(field_id, label, field_type, options, is_required):
    required_mark = " *" if is_required else ""

    if field_type == 'text':
        return st.text_input(label + required_mark, key=f"text_{field_id}")
    elif field_type == 'number':
        return st.number_input(label + required_mark, key=f"number_{field_id}")
    elif field_type == 'dropdown':
        options_list = json.loads(options) if options else []
        return st.selectbox(label + required_mark, options_list, key=f"dropdown_{field_id}")
    elif field_type == 'checkbox':
        return st.checkbox(label + required_mark, key=f"checkbox_{field_id}")
    elif field_type == 'date':
        return st.date_input(label + required_mark, key=f"date_{field_id}")
    else:
        st.warning(f"نوع الحقل غير معروف: {field_type}")
        return None

def process_survey_submission(survey_id, region_id, fields, answers, is_completed, survey_name):
    missing_fields = check_required_fields(fields, answers)

    if missing_fields and is_completed:
        st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
        return

    if is_completed and has_completed_survey_today(st.session_state.user_id, survey_id):
        st.error("لقد قمت بإكمال هذا الاستبيان اليوم بالفعل. يمكنك إكماله مرة أخرى غدًا.")
        return

    response_id = save_response(
        survey_id=survey_id,
        user_id=st.session_state.user_id,
        region_id=region_id,
        is_completed=is_completed
    )

    if not response_id:
        st.error("حدث خطأ أثناء حفظ البيانات")
        return

    save_response_details(response_id, answers)
    show_submission_message(is_completed, survey_name)

def check_required_fields(fields, answers):
    missing_fields = []
    for field in fields:
        field_id, label, _, _, is_required, _ = field
        if is_required and not answers.get(field_id):
            missing_fields.append(label)
    return missing_fields

def save_response_details(response_id, answers):
    for field_id, answer in answers.items():
        if answer is not None:
            save_response_detail(
                response_id=response_id,
                field_id=field_id,
                answer_value=str(answer)
            )

def show_submission_message(is_completed, survey_name):
    if is_completed:
        st.success(f"تم إرسال استبيان '{survey_name}' بنجاح")
        cols = st.columns(3)
        cols[0].info(f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cols[1].info(f"بواسطة: {st.session_state.username}")
        cols[2].info(f"حالة: مكتمل")
    else:
        st.success(f"تم حفظ مسودة استبيان '{survey_name}' بنجاح")

# دالة get_allowed_surveys تم نقلها إلى database.py

def view_survey_responses(survey_id):
    try:
        survey = get_survey_by_id(survey_id) # استخدام الدالة الجديدة

        st.subheader(f"إجابات استبيان {survey['survey_name']} (عرض فقط)")

        # استبدال استدعاء Supabase المباشر
        conn = database.get_db_connection()
        if conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        response_id,
                        submission_date,
                        is_completed
                    FROM
                        Responses
                    WHERE
                        survey_id = %s AND user_id = %s
                    ORDER BY submission_date DESC;
                """, (survey_id, st.session_state.user_id))
                responses = cur.fetchall()
            conn.close()
        else:
            responses = []

        if not responses:
            st.info("لا توجد إجابات مسجلة لهذا الاستبيان")
            return

        df = pd.DataFrame(
            [(r['response_id'], r['submission_date'], "✔️" if r['is_completed'] else "✖️")
             for r in responses],
            columns=["ID", "التاريخ", "الحالة"]
        )

        st.dataframe(df, use_container_width=True)

        selected_response_id = st.selectbox(
            "اختر إجابة لعرض تفاصيلها",
            options=[r['response_id'] for r in responses],
            format_func=lambda x: f"إجابة #{x}"
        )

        if selected_response_id:
            details = get_response_details(selected_response_id) # استخدام الدالة الجديدة

            st.subheader("تفاصيل الإجابة المحددة")
            for detail in details:
                # تفاصيل الإجابة تأتي الآن كـ (detail_id, field_id, label, field_type, options, answer)
                st.write(f"**{detail[2]}:** {detail[5] if detail[5] else 'غير مدخل'}") # detail[2] for label, detail[5] for answer

    except Exception as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
