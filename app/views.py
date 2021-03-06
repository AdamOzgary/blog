from flask import (
    render_template, request,
    redirect, url_for,
    flash, jsonify,
    Response
)
from flask_login import (
    LoginManager, login_required,
    login_user, current_user,
    logout_user
)
from sqlalchemy.exc import IntegrityError
from app import app, db
from .models import User, Post, Category, Tag, Blacklist, Adminlist, Comment,\
        PosteNotFoundError
from .forms import LoginForm, RegisterForm, PostForm
from .utils import admin_required


login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)


@app.route('/')
def main():
    return render_template('main.html', options=Category.get_dict_list())


@app.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit() and request.method == 'POST':
        user = db.session.query(User).filter(
                User.username == form.username.data
                ).first()
                
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('main'))
        
        flash('Invalid username/password', 'error')
        return redirect(url_for('login'))

    return render_template('login.html', form=form)


@app.route('/register/', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit() and request.method == 'POST':
        user = User()
        user.name = form.name.data
        if len(form.lastname.data) > 0:
            user.lastname = form.lastname.data
        user.username = form.username.data
        user.email = form.email.data
        user.set_password(form.password.data)
        
        try: 
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            flash("The system already has an account with the same name and/or mail.")
            return redirect(url_for('register'))

        login_user(user, remember=form.remember.data)
        return redirect(url_for('main'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))


@app.route('/licence')
def licence():
    return '<h2>Теперь мы будем продавать твои данные</h2>'


@app.route('/new-post', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if request.method == 'POST'and form.validate_on_submit():
        try:
            post = Post()
            post.title = form.title.data
            post.category_id = form.category.data
            post.prev_text = form.preview_text.data
            post.content = form.text.data
            post.author_id = current_user.get_id()

            tags = form.tags.data.split()
            post.add_tags(tags)
        except Exception as e:
            print(e.args)

        return redirect(url_for('main'))
    else:
        return render_template('new-post.html',form = form)


@app.route('/posts/<category_id>')
def get_posts(category_id): 
    try: 
        category_id = int(category_id)
        posts = db.session.query(Post).filter(Post.category_id == category_id).all()
    except ValueError:
        posts = db.session.query(Post).all()
    
    return jsonify({'posts': [post.get_dict() for post in posts]})


@app.route('/post/<int:post_id>')
def get_post(post_id: int):
    try: 
        post = Post.get(post_id)
        if not isinstance(post, Post):
            raise PosteNotFoundError
    except PosteNotFoundError:
        return Response(status=404)
    else: 
        is_liked = False
        is_disliked = False
        if current_user.is_authenticated:
            current_user.add_post_to_history(post)
            post_score = current_user.get_post_score(post_id)
            is_liked = post_score['is_liked']
            is_disliked = post_score['is_disliked']
        else:
            # нужно добавить в models отдельный счетчик количества загрузок поста для не зарегистрованных
            pass

    return render_template('post-page.html',
            post = post.get_dict(),
            comments = Comment.get_post_comments(post_id),
            is_liked = is_liked,
            is_disliked = is_disliked
    )


@login_required
@app.route('/post/<int:post_id>/comment-post', methods=["POST"])
def comment_post(post_id:int):
    try:
        request_data = request.get_json()
        comment = Comment.comment_post(post_id,\
                current_user.get_id(), request_data['text'])
    except Exception as e:
        print(e.args)
        return Response(status=404)
    else:
        return jsonify(comment)


@login_required
@app.route('/post/<int:post_id>/like/<int:is_like>', methods=["POST"])
def like_post(post_id: int, is_like):
    if bool(is_like):
        current_user.like_post(post_id)
    else: 
        current_user.dislike_post(post_id)

    post = Post.query.get(post_id)
    post_likes = {
        'likes': post.like_count,
        'dislikes': post.dislike_count, 
        'views': post.view_count,
        'comments': post.comment_count
    }
    return jsonify(post_likes)


@login_required
@app.route('/post/<int:post_id>/like-comment/<int:comment_id>')
def like_comment(post_id: int, comment_id:int):
    return jsonify({"like_count":current_user.like_comment(comment_id)})


@login_required
@app.route('/post/<int:post_id>/reply-comment', methods=["POST"])
def reply_comment(post_id: int):
    try: 
        request_data = request.get_json()
        print(request_data)
        reply = Comment.reply_comment(post_id, \
                current_user.get_id(), request_data['text'], request_data['replyedCommentId'])
    except Exception as e:
        print(e.args)
        return Response(status=404)
    else: 
        return jsonify(reply)

@app.route('/get-categories')
def get_categories():
    return jsonify({'categories': Category.get_dict_list()})


@login_manager.unauthorized_handler
def unauth_handler():
    flash("Authorize please to access to all features")
    return redirect(url_for("login"))

@login_required
@app.route('/add-subscribe/<int:subscribe_id>/')
def add_subscribe(subscribe_id):
    current_user.add_subscribe(subscribe_id)
    return jsonify({'l':[sub.username for sub in current_user.subscriptions]})


@login_required
@app.route('/del-subscribe/<int:subscribe_id>/')
def del_subscribe(subscribe_id):
    current_user.del_subscribe(subscribe_id)
    return jsonify({'l':[sub.username for sub in current_user.subscriptions]})

@app.route('/current-user-info')
@login_required
def get_current_user_info():
    user = db.session.query(User).filter(
        User.id == current_user.get_id()).first()
    return jsonify(user.get_dict())


@app.route('/my-page')
@login_required
def get_my_page():
    return render_template('user_page.html',
            user = current_user.get_dict(),
            description = current_user.get_description(),
            posts = current_user.get_user_posts()
    )


@app.route('/my-posts')
@login_required
def get_my_posts():
    pass


@app.route('/bug-report')
@login_required
def bug_report(): 
    pass


@app.route('/admin')
@login_required
@admin_required
def admin():
    return render_template('admin.html')


@app.route('/favicon.ico')
def favicon():
    return redirect('/static/favicon.ico')


@login_required
@admin_required
@app.route('/get-statistics')
def get_statistics():
    stat = {
        "users": db.session.query(User).count(), 
        "posts": db.session.query(Post).count()
    }
    return jsonify(stat)


@app.route('/from-admin/del-post', methods=['POST'])
@app.route('/from-admin/advertise', methods=['POST'])
@login_required
@admin_required
def some_func():
    print(request.json)
    

@login_required
@admin_required
@app.route('/from-admin/new-category', methods=['POST'])
def admin_new_category():
    new_category = Category(name = request.json['name'])
    db.session.add(new_category)
    db.session.commit()
    return Response(status=200)
    

@login_required
@admin_required
@app.route('/from-admin/del-categories', methods=['POST'])
def admin_del_category():
    category_id_list = [int(id) for id in request.json['categories']]
    category_list = []

    for id in category_id_list:
        db.session.delete(db.session.query(Category).filter(Category.id == id).first())
    db.session.commit()
    print(category_list, category_id_list)
    return Response(status=200)


@login_required
@admin_required
@app.route('/from-admin/add-admin', methods=['POST'])
def admin_new_admin():
    admin_username = request.json['username']

    try:
        new_admin = db.session.query(User).\
            filter(User.username == admin_username).first()
        new_admin.is_admin = True
        db.session.add(new_admin)
        db.session.commit()
        return Response(status=200)
    except TypeError:
        return Response(status=404)


@login_required
@admin_required
@app.route('/from-admin/user-lockdown', methods=['POST'])
def user_lockdown():
    username = request.json['username']
    user = User.get_user_by_username(username)
    try: 
        blacklist_item = Blacklist(user_id = user.id, 
                user = user, 
                blacklist_period = int(request.json['period'])
        )
        db.session.add(blacklist_item)
        db.session.commit()
        print(user.id)
    except Exception:
        print(request.json['username'], request.json['period'])
        return Response(status=404)
    else: 
        return Response(status=200)