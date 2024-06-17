import csv
from io import BytesIO
from flask import Blueprint, render_template, request, send_file

from math import ceil

bp = Blueprint('user_actions', __name__, url_prefix='/user_actions')
MAX_PER_PAGE = 10

@bp.route('/')
def index():
    from app import db_connector
    page = request.args.get('page', 1, type=int)
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = ("SELECT surname, name, last_name, "
                 "path, visit_logs.created_at AS created_at "
                 "FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
                 f"LIMIT {MAX_PER_PAGE} OFFSET {(page - 1) * MAX_PER_PAGE}")
        cursor.execute(query)
        user_actions = cursor.fetchall()

        query = "SELECT COUNT(*) as count FROM visit_logs"
        cursor.execute(query)
        record_count = cursor.fetchone().count
        page_count = ceil(record_count / MAX_PER_PAGE)
        pages = range(max(1, page - 3), min(page_count, page + 3)+1)
    return render_template("user_actions/index.html", user_actions=user_actions, 
                            page=page, pages=pages, page_count=page_count)

@bp.route('users_stats')
def users_stats():
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = ("SELECT users.user_id, users.name, users.last_name, users.surname, "
         "COUNT(*) AS entries_counter "
         "FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
         "GROUP BY users.user_id")
        cursor.execute(query)
        print(cursor.statement)
        users_stats = cursor.fetchall()
    return render_template("user_actions/users_stats.html", users_stats=users_stats)
@bp.route('paths_stats')
def paths_stats():
    
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
         query = ("select name, last_name, surname, "
                  "path, visit_logs.created_at as created_at "
                  "from visit_logs left join users on visit_logs.user_id = users.user_id")
         cursor.execute(query)
         user_actions = cursor.fetchall()
    return render_template("user_actions/paths_stats.html")
@bp.route('user_export.csv')

def user_export():
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = ("SELECT users.user_id, users.name, users.last_name, users.surname, "
         "COUNT(*) AS entries_counter "
         "FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
         "GROUP BY users.user_id")
        cursor.execute(query)
        print(cursor.statement)
        users_stats = cursor.fetchall()
        result = ''
        fields = ['last_name', 'name', 'surname', 'entries_counter']
        none_values = ['не', 'авторизованный', 'пользователь']
        result += ','.join(fields)+'\n'
        for record in users_stats:
            if record.user_id is None:
                result += ','.join(none_values)+','+str(record.entries_counter)+'\n'
                continue
            result += ','.join([str(getattr(record, field)) for field in fields])+'\n'
    return send_file(BytesIO(result.encode()), as_attachment=True, mimetype='text/csv', download_name='user_export.csv')
        

    