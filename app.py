from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Category, Product, Cart, CartItem, Order, OrderItem
from config import Config
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from werkzeug.security import generate_password_hash
from sqlalchemy import func, extract
from PIL import Image
from pdf_utils import build_receipt_pdf, build_statistics_report_pdf
import io
import os
import uuid

app = Flask(__name__)
app.config.from_object(Config)

# ==================== Загрузка изображений товаров ====================
# Файлы сохраняются локально в static/uploads/products/
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads', 'products')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # ограничение размера загрузки — 8 МБ
ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGE_SIDE = 1000  # макс. сторона изображения товара, px


def _allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT

def save_product_image(file_storage):
    """Проверяет, нормализует и сохраняет загруженное изображение товара.

    Возвращает имя сохранённого файла или None, если файл не выбран.
    Бросает ValueError при некорректном файле.
    """
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_image(file_storage.filename):
        raise ValueError('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, WEBP, GIF.')

    file_storage.stream.seek(0)
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except Exception:
        raise ValueError('Загруженный файл не является корректным изображением.')

    # Уменьшаем слишком большие изображения
    if max(img.size) > MAX_IMAGE_SIDE:
        ratio = MAX_IMAGE_SIDE / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        fname = f"{uuid.uuid4().hex}.png"
        img.save(os.path.join(UPLOAD_FOLDER, fname), 'PNG', optimize=True)
    else:
        img = img.convert('RGB')
        fname = f"{uuid.uuid4().hex}.jpg"
        img.save(os.path.join(UPLOAD_FOLDER, fname), 'JPEG', quality=88, optimize=True)
    return fname


def delete_product_image(filename):
    """Удаляет локальный файл изображения товара (внешние URL игнорируются)."""
    if filename and not filename.startswith(('http://', 'https://')):
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('У вас нет прав для доступа к этой странице.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== Главная страница ====================
@app.route('/')
def index():
    """Главная страница"""
    featured_products = Product.query.filter(Product.stock_quantity > 0).limit(8).all()
    categories = Category.query.filter_by(parent_category_id=None).all()
    return render_template('index.html', featured_products=featured_products, categories=categories)

# ==================== Авторизация и регистрация ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        fio = request.form.get('fio')
        phone = request.form.get('phone')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует.', 'danger')
            return render_template('register.html')
        
        user = User(email=email, fio=fio, phone=phone, role='user')
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Неверный email или пароль.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('index'))

# ==================== Каталог ====================
@app.route('/catalog')
def catalog():
    """Каталог товаров"""
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')
    
    query = Product.query
    
    if category_id:
        category = Category.query.get(category_id)
        if category:
            category_ids = [category_id]
            def get_child_categories(parent_id):
                children = Category.query.filter_by(parent_category_id=parent_id).all()
                for child in children:
                    category_ids.append(child.id)
                    get_child_categories(child.id)
            get_child_categories(category_id)
            query = query.filter(Product.category_id.in_(category_ids))
    
    if search:
        query = query.filter(
            Product.name.contains(search) | 
            Product.description.contains(search) |
            Product.article.contains(search)
        )
    
    products = query.all()
    categories = Category.query.all()
    
    return render_template('catalog.html', products=products, categories=categories, 
                         selected_category=category_id, search=search)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Детальная страница товара"""
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

# ==================== Корзина ====================
@app.route('/cart')
@login_required
def cart():
    """Корзина пользователя"""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    return render_template('cart.html', cart=cart)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Добавить товар в корзину"""
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if quantity <= 0:
        flash('Количество должно быть больше нуля.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    if product.stock_quantity < quantity:
        flash('Недостаточно товара на складе.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
        if cart_item.quantity > product.stock_quantity:
            cart_item.quantity = product.stock_quantity
            flash('Добавлено максимально доступное количество товара.', 'warning')
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
            price_at_add=product.price
        )
        db.session.add(cart_item)
    
    db.session.commit()
    flash('Товар добавлен в корзину.', 'success')
    return redirect(url_for('cart'))

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    """Обновить количество товара в корзине"""
    cart_item = CartItem.query.get_or_404(item_id)
    cart = Cart.query.get_or_404(cart_item.cart_id)
    
    if cart.user_id != current_user.id:
        flash('Ошибка доступа.', 'danger')
        return redirect(url_for('cart'))
    
    quantity = int(request.form.get('quantity', 1))
    
    if quantity <= 0:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Товар удален из корзины.', 'info')
        return redirect(url_for('cart'))
    
    if cart_item.product.stock_quantity < quantity:
        flash('Недостаточно товара на складе.', 'danger')
        return redirect(url_for('cart'))
    
    cart_item.quantity = quantity
    db.session.commit()
    flash('Корзина обновлена.', 'success')
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Удалить товар из корзины"""
    cart_item = CartItem.query.get_or_404(item_id)
    cart = Cart.query.get_or_404(cart_item.cart_id)
    
    if cart.user_id != current_user.id:
        flash('Ошибка доступа.', 'danger')
        return redirect(url_for('cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    flash('Товар удален из корзины.', 'info')
    return redirect(url_for('cart'))

@app.route('/api/cart/add/<int:product_id>', methods=['POST'])
@login_required
def api_add_to_cart(product_id):
    """AJAX-добавление товара в корзину (для попапа на карте планет). Возвращает JSON."""
    product = Product.query.get_or_404(product_id)

    if product.stock_quantity < 1:
        return jsonify(success=False, message='Товара нет в наличии.')

    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()

    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    if cart_item:
        if cart_item.quantity + 1 > product.stock_quantity:
            return jsonify(success=False, message='Больше нет в наличии.',
                           cart_count=sum(i.quantity for i in cart.items))
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product_id,
                             quantity=1, price_at_add=product.price)
        db.session.add(cart_item)

    db.session.commit()
    return jsonify(success=True,
                   message=f'«{product.name}» — добавлено в корзину',
                   cart_count=sum(i.quantity for i in cart.items))

# ==================== Карта планет (книжная галактика) ====================
PLANET_UNLOCK_THRESHOLD = 3  # сколько книг купить, чтобы «исследовать» планету

@app.route('/map')
@login_required
def planet_map():
    """Интерактивная карта планет: категории товаров как достижения."""
    # «Планеты» — листовые категории (без подкатегорий), у которых есть товары
    all_categories = Category.query.order_by(Category.id).all()
    parent_ids = {c.parent_category_id for c in all_categories if c.parent_category_id}
    leaf_categories = [c for c in all_categories if c.id not in parent_ids]

    # Сколько штук куплено пользователем по каждой категории (оформленные заказы)
    rows = db.session.query(
        Product.category_id,
        func.sum(OrderItem.quantity)
    ).join(OrderItem, OrderItem.product_id == Product.id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.user_id == current_user.id, Order.status != 'cancelled')\
     .group_by(Product.category_id).all()
    bought = {cid: int(q or 0) for cid, q in rows}

    planets = []
    explored_ids = set()
    for cat in leaf_categories:
        products = Product.query.filter_by(category_id=cat.id).order_by(Product.name).all()
        if not products:
            continue  # пустые категории планетами не показываем
        count = bought.get(cat.id, 0)
        explored = count >= PLANET_UNLOCK_THRESHOLD
        if explored:
            explored_ids.add(cat.id)
        planets.append({
            'id': cat.id,
            'name': cat.name,
            'products': products,
            'count': count,
            'progress': min(count, PLANET_UNLOCK_THRESHOLD),
            'explored': explored,
        })

    # Какие планеты открылись с прошлого визита — для анимации разблокировки
    prev = set(session.get('explored_planets', []))
    newly_ids = explored_ids - prev
    session['explored_planets'] = list(explored_ids)
    newly = [p['name'] for p in planets if p['id'] in newly_ids]

    return render_template('planets.html', planets=planets,
                           threshold=PLANET_UNLOCK_THRESHOLD, newly=newly)

# ==================== Заказы ====================
@app.route('/cart/checkout', methods=['POST'])
@login_required
def checkout():
    """Оформить заказ"""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    
    if not cart or not cart.items:
        flash('Корзина пуста.', 'warning')
        return redirect(url_for('cart'))
    
    # Проверяем наличие товаров
    for item in cart.items:
        if item.product.stock_quantity < item.quantity:
            flash(f'Недостаточно товара "{item.product.name}" на складе.', 'danger')
            return redirect(url_for('cart'))
    
    # Создаем заказ
    total_amount = cart.get_total()
    order = Order(
        user_id=current_user.id,
        status='pending',
        total_amount=total_amount
    )
    db.session.add(order)
    db.session.flush()
    
    # Создаем позиции заказа и уменьшаем количество товаров
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_per_unit=item.price_at_add
        )
        db.session.add(order_item)
        item.product.stock_quantity -= item.quantity
    
    # Очищаем корзину
    CartItem.query.filter_by(cart_id=cart.id).delete()
    
    db.session.commit()
    
    flash('Заказ успешно оформлен! Чек будет скачан автоматически.', 'success')
    # Редиректим на страницу заказа с параметром для автоматической загрузки чека
    return redirect(url_for('order_detail', order_id=order.id, download_receipt=1))

@app.route('/order/<int:order_id>/receipt')
@login_required
def generate_receipt(order_id):
    """Генерировать и скачать чек заказа"""
    order = Order.query.get_or_404(order_id)
    
    # Проверяем права доступа
    if order.user_id != current_user.id and not current_user.is_admin():
        flash('Ошибка доступа.', 'danger')
        return redirect(url_for('index'))

    # Формируем стилизованный PDF-чек
    pdf_bytes = build_receipt_pdf(order, get_order_status_name(order.status))
    receipt_file = io.BytesIO(pdf_bytes)

    filename = f"receipt_order_{order.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        receipt_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

def get_order_status_name(status):
    """Получить название статуса заказа"""
    status_names = {
        'pending': 'Ожидает обработки',
        'processing': 'В обработке',
        'shipped': 'Отправлен',
        'delivered': 'Доставлен',
        'cancelled': 'Отменен'
    }
    return status_names.get(status, status)

@app.route('/orders')
@login_required
def orders():
    """История заказов пользователя"""
    orders_list = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders_list)

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    """Детали заказа"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin():
        flash('Ошибка доступа.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('order_detail.html', order=order)

# ==================== Профиль ====================
@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    return render_template('profile.html')

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Обновить профиль пользователя"""
    current_user.fio = request.form.get('fio')
    current_user.phone = request.form.get('phone')
    current_user.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    flash('Профиль успешно обновлен.', 'success')
    return redirect(url_for('profile'))

# ==================== Админ-панель ====================
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Главная страница админ-панели"""
    stats = {
        'users_count': User.query.count(),
        'products_count': Product.query.count(),
        'orders_count': Order.query.count(),
        'categories_count': Category.query.count()
    }
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)

# Управление категориями
@app.route('/admin/categories')
@admin_required
def admin_categories():
    """Управление категориями"""
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET', 'POST'])
@admin_required
def admin_add_category():
    """Добавить категорию"""
    if request.method == 'POST':
        name = request.form.get('name')
        parent_id = request.form.get('parent_id', type=int) or None
        
        category = Category(name=name, parent_category_id=parent_id)
        db.session.add(category)
        db.session.commit()
        
        flash('Категория успешно добавлена.', 'success')
        return redirect(url_for('admin_categories'))
    
    categories = Category.query.all()
    return render_template('admin/add_category.html', categories=categories)

@app.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_category(category_id):
    """Редактировать категорию"""
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.parent_category_id = request.form.get('parent_id', type=int) or None
        db.session.commit()
        
        flash('Категория успешно обновлена.', 'success')
        return redirect(url_for('admin_categories'))
    
    categories = Category.query.filter(Category.id != category_id).all()
    return render_template('admin/edit_category.html', category=category, categories=categories)

@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_delete_category(category_id):
    """Удалить категорию"""
    category = Category.query.get_or_404(category_id)
    
    if category.products:
        flash('Нельзя удалить категорию, в которой есть товары.', 'danger')
        return redirect(url_for('admin_categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Категория успешно удалена.', 'success')
    return redirect(url_for('admin_categories'))

# Управление товарами
@app.route('/admin/products')
@admin_required
def admin_products():
    """Управление товарами"""
    products = Product.query.all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    """Добавить товар"""
    if request.method == 'POST':
        article = request.form.get('article')
        name = request.form.get('name')
        description = request.form.get('description')
        price = Decimal(request.form.get('price'))
        stock_quantity = int(request.form.get('stock_quantity', 0))
        category_id = int(request.form.get('category_id'))
        
        if Product.query.filter_by(article=article).first():
            flash('Товар с таким артикулом уже существует.', 'danger')
            return redirect(url_for('admin_add_product'))

        try:
            image_filename = save_product_image(request.files.get('image'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('admin_add_product'))

        product = Product(
            article=article,
            name=name,
            description=description,
            price=price,
            stock_quantity=stock_quantity,
            image_url=image_filename,
            category_id=category_id
        )
        db.session.add(product)
        db.session.commit()
        
        flash('Товар успешно добавлен.', 'success')
        return redirect(url_for('admin_products'))
    
    categories = Category.query.all()
    return render_template('admin/add_product.html', categories=categories)

@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    """Редактировать товар"""
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.article = request.form.get('article')
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = Decimal(request.form.get('price'))
        product.stock_quantity = int(request.form.get('stock_quantity', 0))
        product.category_id = int(request.form.get('category_id'))
        product.updated_at = datetime.now(timezone.utc)

        # Обработка изображения: замена новым файлом, удаление или сохранение текущего
        try:
            new_image = save_product_image(request.files.get('image'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('admin_edit_product', product_id=product_id))

        if new_image:
            delete_product_image(product.image_url)
            product.image_url = new_image
        elif request.form.get('remove_image') == '1':
            delete_product_image(product.image_url)
            product.image_url = None

        db.session.commit()
        flash('Товар успешно обновлен.', 'success')
        return redirect(url_for('admin_products'))
    
    categories = Category.query.all()
    return render_template('admin/edit_product.html', product=product, categories=categories)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    """Удалить товар"""
    product = Product.query.get_or_404(product_id)

    delete_product_image(product.image_url)
    db.session.delete(product)
    db.session.commit()

    flash('Товар успешно удален.', 'success')
    return redirect(url_for('admin_products'))

# Управление пользователями
@app.route('/admin/users')
@admin_required
def admin_users():
    """Управление пользователями"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    """Добавить пользователя"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        fio = request.form.get('fio')
        phone = request.form.get('phone')
        role = request.form.get('role', 'user')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует.', 'danger')
            return redirect(url_for('admin_add_user'))
        
        user = User(email=email, fio=fio, phone=phone, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Пользователь успешно добавлен.', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/add_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    """Редактировать пользователя"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.fio = request.form.get('fio')
        user.phone = request.form.get('phone')
        user.role = request.form.get('role', 'user')
        user.updated_at = datetime.now(timezone.utc)
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
        
        db.session.commit()
        flash('Пользователь успешно обновлен.', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Удалить пользователя"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Вы не можете удалить свой собственный аккаунт.', 'danger')
        return redirect(url_for('admin_edit_user', user_id=user_id))
    
    admin_count = User.query.filter_by(role='admin').count()
    if user.is_admin() and admin_count <= 1:
        flash('Нельзя удалить последнего администратора.', 'danger')
        return redirect(url_for('admin_edit_user', user_id=user_id))
    
    db.session.delete(user)
    db.session.commit()
    
    flash('Пользователь успешно удален.', 'success')
    return redirect(url_for('admin_users'))

# Управление заказами
@app.route('/admin/orders')
@admin_required
def admin_orders():
    """Управление заказами"""
    orders_list = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders_list)

@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    """Детали заказа для администратора"""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/orders/<int:order_id>/update_status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    """Обновить статус заказа"""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    if new_status in valid_statuses:
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Статус заказа успешно обновлен.', 'success')
    else:
        flash('Неверный статус.', 'danger')
    
    return redirect(url_for('admin_order_detail', order_id=order_id))

# Статистика
@app.route('/admin/statistics')
@admin_required
def admin_statistics():
    """Страница статистики для администратора"""
    # Общая статистика
    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total_amount)).filter(Order.status != 'cancelled').scalar() or Decimal('0')
    
    # Статистика по заказам за последние 30 дней
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    orders_last_30_days = Order.query.filter(Order.created_at >= thirty_days_ago).count()
    revenue_last_30_days = db.session.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= thirty_days_ago,
        Order.status != 'cancelled'
    ).scalar() or Decimal('0')
    
    # Статистика по дням за последние 7 дней для графика
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_stats = db.session.query(
        func.date(Order.created_at).label('date'),
        func.count(Order.id).label('orders_count'),
        func.sum(Order.total_amount).label('revenue')
    ).filter(
        Order.created_at >= seven_days_ago,
        Order.status != 'cancelled'
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at)).all()
    
    # Подготовка данных для графика
    dates = []
    orders_data = []
    revenue_data = []
    
    for i in range(7):
        date = (datetime.now(timezone.utc) - timedelta(days=6-i)).date()
        dates.append(date.strftime('%d.%m'))
        orders_data.append(0)
        revenue_data.append(0)
    
    for stat in daily_stats:
        if isinstance(stat.date, str):
            from datetime import datetime as dt
            stat_date = dt.strptime(stat.date, '%Y-%m-%d').date()
        else:
            stat_date = stat.date
        
        date_str = stat_date.strftime('%d.%m')
        if date_str in dates:
            idx = dates.index(date_str)
            orders_data[idx] = stat.orders_count
            revenue_data[idx] = float(stat.revenue or 0)
    
    # Статистика по статусам заказов
    status_stats = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()
    
    status_data = {status: count for status, count in status_stats}
    
    # Топ товаров по продажам
    top_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.quantity * OrderItem.price_per_unit).label('revenue')
    ).join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.status != 'cancelled')\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(10).all()
    
    return render_template('admin/statistics.html',
                         total_users=total_users,
                         total_products=total_products,
                         total_orders=total_orders,
                         total_revenue=f"{float(total_revenue):.2f}",
                         orders_last_30_days=orders_last_30_days,
                         revenue_last_30_days=f"{float(revenue_last_30_days):.2f}",
                         dates=dates,
                         orders_data=orders_data,
                         revenue_data=revenue_data,
                         status_data=status_data,
                         top_products=[(p.name, p.total_sold, f"{float(p.revenue):.2f}") for p in top_products])

@app.route('/admin/statistics/download_report')
@admin_required
def download_statistics_report():
    """Скачать отчет по статистике в формате TXT"""
    # Общая статистика
    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total_amount)).filter(Order.status != 'cancelled').scalar() or Decimal('0')
    
    # Статистика за последние 30 дней
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    orders_last_30_days = Order.query.filter(Order.created_at >= thirty_days_ago).count()
    revenue_last_30_days = db.session.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= thirty_days_ago,
        Order.status != 'cancelled'
    ).scalar() or Decimal('0')
    
    # Статистика по статусам
    status_stats = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()
    
    # Топ товаров
    top_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.quantity * OrderItem.price_per_unit).label('revenue')
    ).join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.status != 'cancelled')\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(10).all()
    
    # Формируем стилизованный PDF-отчёт
    status_names = {
        'pending': 'Ожидает обработки',
        'processing': 'В обработке',
        'shipped': 'Отправлен',
        'delivered': 'Доставлен',
        'cancelled': 'Отменен'
    }
    data = {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'orders_last_30_days': orders_last_30_days,
        'revenue_last_30_days': revenue_last_30_days,
        'status_rows': [(status_names.get(status, status), count) for status, count in status_stats],
        'top_products': [(name, sold, revenue) for name, sold, revenue in top_products],
    }

    pdf_bytes = build_statistics_report_pdf(data)
    report_file = io.BytesIO(pdf_bytes)

    filename = f"statistics_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        report_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# ==================== Инициализация базы данных ====================
def init_db():
    """Создать таблицы в базе данных и автоматически создать администратора"""
    import os
    from config import Config
    
    with app.app_context():
        # Получаем путь к базе данных из конфигурации
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        
        # Извлекаем путь к файлу из URI
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
        elif db_uri.startswith('sqlite://'):
            db_path = db_uri.replace('sqlite://', '')
        else:
            db_path = db_uri
        
        # Нормализуем путь (преобразуем в абсолютный)
        db_path = os.path.abspath(db_path)
        
        # Создаем папку, если её нет
        instance_dir = os.path.dirname(db_path)
        if instance_dir and not os.path.exists(instance_dir):
            os.makedirs(instance_dir, exist_ok=True)
            print(f"Создана папка: {instance_dir}")
        
        # Проверяем существование файла
        db_exists = os.path.exists(db_path)
        
        # Создаем таблицы (db.create_all() безопасен - не пересоздает существующие таблицы)
        try:
            db.create_all()
        except Exception as e:
            print(f"Ошибка при создании таблиц: {e}")
            print(f"Путь к БД: {db_path}")
            print(f"URI: {db_uri}")
            raise
        
        if db_exists:
            print(f"База данных уже существует: {db_path}")
            admin = User.query.filter_by(email='admin@planeta.ru').first()
            if admin:
                print("Администратор уже существует. Пропускаем создание.")
                return
            else:
                print("Администратор не найден. Создаем администратора...")
        else:
            print("База данных не найдена. Создаем новую базу данных.")
            print("Таблицы базы данных созданы.")
        
        admin = User.query.filter_by(email='admin@planeta.ru').first()
        if not admin:
            # Создаем администратора
            admin = User(
                email='admin@planeta.ru',
                password_hash=generate_password_hash('admin123'),
                fio='Администратор Системы',
                phone='+7 (347) 200-00-01',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Администратор создан: admin@planeta.ru / admin123")
            if not db_exists:
                print("База данных готова к использованию (пустая, только администратор).")
        else:
            print("Администратор уже существует.")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)