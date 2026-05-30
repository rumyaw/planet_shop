from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Category, Product, Cart, CartItem, Order, OrderItem
from config import Config
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from werkzeug.security import generate_password_hash
from sqlalchemy import func, extract
import io

app = Flask(__name__)
app.config.from_object(Config)

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
    # Получаем несколько популярных товаров для главной страницы
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
        # Получаем категорию и все её подкатегории
        category = Category.query.get(category_id)
        if category:
            # Собираем ID всех подкатегорий (рекурсивно)
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
    
    # Формируем чек
    receipt_lines = []
    receipt_lines.append("=" * 60)
    receipt_lines.append("ЧЕК ОПЛАТЫ")
    receipt_lines.append("Книжная сеть 'Планета'")
    receipt_lines.append("=" * 60)
    receipt_lines.append("")
    receipt_lines.append(f"Номер заказа: #{order.id}")
    receipt_lines.append(f"Дата оформления: {order.created_at.strftime('%d.%m.%Y %H:%M:%S')}")
    receipt_lines.append("")
    receipt_lines.append(f"Покупатель: {order.user.fio}")
    receipt_lines.append(f"Email: {order.user.email}")
    if order.user.phone:
        receipt_lines.append(f"Телефон: {order.user.phone}")
    receipt_lines.append("")
    receipt_lines.append("-" * 60)
    receipt_lines.append("ТОВАРЫ:")
    receipt_lines.append("-" * 60)
    
    for item in order.items:
        receipt_lines.append(f"{item.product.name}")
        receipt_lines.append(f"  Артикул: {item.product.article}")
        receipt_lines.append(f"  Количество: {item.quantity} шт.")
        receipt_lines.append(f"  Цена за единицу: {item.price_per_unit:.2f} ₽")
        receipt_lines.append(f"  Сумма: {item.get_subtotal():.2f} ₽")
        receipt_lines.append("")
    
    receipt_lines.append("-" * 60)
    receipt_lines.append(f"ИТОГО К ОПЛАТЕ: {order.total_amount:.2f} ₽")
    receipt_lines.append("")
    receipt_lines.append(f"Статус заказа: {get_order_status_name(order.status)}")
    receipt_lines.append("")
    receipt_lines.append("=" * 60)
    receipt_lines.append("Спасибо за покупку!")
    receipt_lines.append("=" * 60)
    
    # Создаем файл в памяти
    receipt_text = "\n".join(receipt_lines)
    receipt_bytes = receipt_text.encode('utf-8')
    receipt_file = io.BytesIO(receipt_bytes)
    
    filename = f"receipt_order_{order.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    
    return send_file(
        receipt_file,
        mimetype='text/plain',
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
        
        image_url = request.form.get('image_url', '').strip() or None
        
        product = Product(
            article=article,
            name=name,
            description=description,
            price=price,
            stock_quantity=stock_quantity,
            image_url=image_url,
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
        product.image_url = request.form.get('image_url', '').strip() or None
        product.category_id = int(request.form.get('category_id'))
        product.updated_at = datetime.now(timezone.utc)
        
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
    
    # Удаляем товар
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
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        flash('Вы не можете удалить свой собственный аккаунт.', 'danger')
        return redirect(url_for('admin_edit_user', user_id=user_id))
    
    # Нельзя удалить последнего администратора
    admin_count = User.query.filter_by(role='admin').count()
    if user.is_admin() and admin_count <= 1:
        flash('Нельзя удалить последнего администратора.', 'danger')
        return redirect(url_for('admin_edit_user', user_id=user_id))
    
    # Удаляем пользователя (каскадное удаление корзин и заказов настроено в моделях)
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
        # stat.date может быть строкой (SQLite возвращает строку) или date объектом
        if isinstance(stat.date, str):
            # Преобразуем строку в date объект
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
    
    # Формируем отчет
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("ОТЧЕТ ПО СТАТИСТИКЕ МАГАЗИНА 'ПЛАНЕТА'")
    report_lines.append("=" * 60)
    report_lines.append(f"Дата формирования: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M:%S')}")
    report_lines.append("")
    
    report_lines.append("ОБЩАЯ СТАТИСТИКА")
    report_lines.append("-" * 60)
    report_lines.append(f"Всего пользователей: {total_users}")
    report_lines.append(f"Всего товаров: {total_products}")
    report_lines.append(f"Всего заказов: {total_orders}")
    report_lines.append(f"Общая выручка: {total_revenue:.2f} ₽")
    report_lines.append("")
    
    report_lines.append("СТАТИСТИКА ЗА ПОСЛЕДНИЕ 30 ДНЕЙ")
    report_lines.append("-" * 60)
    report_lines.append(f"Заказов: {orders_last_30_days}")
    report_lines.append(f"Выручка: {revenue_last_30_days:.2f} ₽")
    report_lines.append("")
    
    report_lines.append("СТАТИСТИКА ПО СТАТУСАМ ЗАКАЗОВ")
    report_lines.append("-" * 60)
    status_names = {
        'pending': 'Ожидает обработки',
        'processing': 'В обработке',
        'shipped': 'Отправлен',
        'delivered': 'Доставлен',
        'cancelled': 'Отменен'
    }
    for status, count in status_stats:
        status_name = status_names.get(status, status)
        report_lines.append(f"{status_name}: {count}")
    report_lines.append("")
    
    report_lines.append("ТОП-10 ТОВАРОВ ПО ПРОДАЖАМ")
    report_lines.append("-" * 60)
    for i, (name, sold, revenue) in enumerate(top_products, 1):
        report_lines.append(f"{i}. {name}")
        report_lines.append(f"   Продано: {sold} шт.")
        report_lines.append(f"   Выручка: {float(revenue):.2f} ₽")
        report_lines.append("")
    
    report_lines.append("=" * 60)
    report_lines.append("Конец отчета")
    report_lines.append("=" * 60)
    
    # Создаем файл в памяти
    report_text = "\n".join(report_lines)
    report_bytes = report_text.encode('utf-8')
    report_file = io.BytesIO(report_bytes)
    
    filename = f"statistics_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    
    return send_file(
        report_file,
        mimetype='text/plain',
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
            # Проверяем, есть ли уже администратор
            admin = User.query.filter_by(email='admin@planeta.ru').first()
            if admin:
                print("Администратор уже существует. Пропускаем создание.")
                return
            else:
                print("Администратор не найден. Создаем администратора...")
        else:
            print("База данных не найдена. Создаем новую базу данных.")
            print("Таблицы базы данных созданы.")
        
        # Проверяем еще раз перед созданием (на всякий случай)
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