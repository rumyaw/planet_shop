"""
Скрипт для автоматического заполнения базы данных тестовыми данными
для интернет-магазина книжной сети "Планета"
Примечание: База данных и администратор создаются автоматически в app.py
"""

from app import app, db
from models import User, Category, Product, Cart, CartItem, Order, OrderItem
from werkzeug.security import generate_password_hash
from decimal import Decimal
from datetime import datetime, timedelta
import random

def fill_database():
    """Заполнить базу данных тестовыми данными"""
    
    with app.app_context():
        # Создаем таблицы, если их еще нет
        try:
            db.create_all()
            print("Таблицы базы данных созданы/проверены.")
        except Exception as e:
            print(f"Ошибка при создании таблиц: {e}")
            return
        
        # Проверяем, есть ли уже данные
        try:
            if Product.query.count() > 0:
                print("База данных уже заполнена. Пропускаем заполнение.")
                return
        except Exception as e:
            print(f"Ошибка при проверке данных: {e}")
            print("Продолжаем заполнение...")
        
        # ==================== 1. Создание пользователей ====================
        print("Создание пользователей...")
        
        # Обычные пользователи
        users_data = [
            {'email': 'ivanov@example.com', 'fio': 'Иванов Иван Иванович', 'phone': '+7 (347) 200-10-01'},
            {'email': 'petrov@example.com', 'fio': 'Петров Петр Петрович', 'phone': '+7 (347) 200-10-02'},
            {'email': 'sidorov@example.com', 'fio': 'Сидоров Сидор Сидорович', 'phone': '+7 (347) 200-10-03'},
            {'email': 'smirnova@example.com', 'fio': 'Смирнова Анна Владимировна', 'phone': '+7 (347) 200-10-04'},
            {'email': 'kozlov@example.com', 'fio': 'Козлов Дмитрий Сергеевич', 'phone': '+7 (347) 200-10-05'},
        ]
        
        users = []
        for user_data in users_data:
            # Проверяем, существует ли пользователь
            if not User.query.filter_by(email=user_data['email']).first():
                user = User(
                    email=user_data['email'],
                    password_hash=generate_password_hash('user123'),
                    fio=user_data['fio'],
                    phone=user_data['phone'],
                    role='user'
                )
                db.session.add(user)
                users.append(user)
        
        db.session.commit()
        print(f"Создано пользователей: {len(users)}")
        
        # ==================== 2. Создание категорий ====================
        print("Создание категорий...")
        
        # Основные категории
        categories_data = [
            {'name': 'Книги'},
            {'name': 'Канцтовары'},
            {'name': 'Подарочные издания'},
        ]
        
        main_categories = []
        for cat_data in categories_data:
            category = Category.query.filter_by(name=cat_data['name']).first()
            if not category:
                category = Category(name=cat_data['name'])
                db.session.add(category)
            main_categories.append(category)
        
        db.session.commit()
        
        # Подкатегории для книг
        book_subcategories_data = [
            {'name': 'Художественная литература', 'parent': main_categories[0]},
            {'name': 'Детская литература', 'parent': main_categories[0]},
            {'name': 'Научная литература', 'parent': main_categories[0]},
            {'name': 'Учебники и пособия', 'parent': main_categories[0]},
            {'name': 'Бизнес-литература', 'parent': main_categories[0]},
        ]
        
        # Подкатегории для канцтоваров
        office_subcategories_data = [
            {'name': 'Ручки и карандаши', 'parent': main_categories[1]},
            {'name': 'Тетради и блокноты', 'parent': main_categories[1]},
            {'name': 'Папки и файлы', 'parent': main_categories[1]},
            {'name': 'Офисные принадлежности', 'parent': main_categories[1]},
        ]
        
        book_subcategory_objects = []
        office_subcategory_objects = []
        
        for subcat_data in book_subcategories_data:
            category = Category.query.filter_by(name=subcat_data['name']).first()
            if not category:
                category = Category(
                    name=subcat_data['name'],
                    parent_category_id=subcat_data['parent'].id
                )
                db.session.add(category)
            book_subcategory_objects.append(category)
        
        for subcat_data in office_subcategories_data:
            category = Category.query.filter_by(name=subcat_data['name']).first()
            if not category:
                category = Category(
                    name=subcat_data['name'],
                    parent_category_id=subcat_data['parent'].id
                )
                db.session.add(category)
            office_subcategory_objects.append(category)
        
        db.session.commit()
        print(f"Категории готовы")
        
        # ==================== 3. Создание товаров (50 штук) ====================
        print("Создание товаров...")
        
        # Изображения книг
        book_images = [
            'https://i.pinimg.com/736x/06/d9/40/06d940ad0946e949a500e8f98626d949.jpg',  # Война и мир
            'https://i.pinimg.com/736x/14/f2/63/14f263f72aa11bfa2bf41b97f50b3e69.jpg',  # Преступление и наказание
            'https://i.pinimg.com/1200x/e0/d5/53/e0d5531461db7c4707c7ffce700a4357.jpg',  # Мастер и Маргарита
            'https://i.pinimg.com/1200x/32/59/36/325936cc6bb0a915fdc84bdbf553be3d.jpg',  # 1984
            'https://i.pinimg.com/736x/4f/e9/04/4fe904ed3618cea54ba3dca8d57f1b99.jpg', # Анна Каренина
            'https://i.pinimg.com/1200x/ac/c6/40/acc6404d8de241e9983fcf5a534f8d1d.jpg', # Идиот
            'https://i.pinimg.com/1200x/48/44/93/484493420598b6eacaf7866d6de03ae0.jpg',  # Отцы и дети
            'https://i.pinimg.com/736x/9f/d1/0e/9fd10e71dee29212d7019e56051bde8b.jpg',  # Евгений Онегин
            'https://i.pinimg.com/736x/20/23/10/202310dd614b62b84be9c597dadb41ea.jpg',  # Обломов
            'https://i.pinimg.com/736x/fe/32/26/fe3226b8ad7162b70d1bf5a301a31f1f.jpg',  # Герой нашего времени
            'https://i.pinimg.com/736x/e3/cf/2f/e3cf2f0b97e5ab74a7096654d220d70c.jpg',  # Тихий Дон
            'https://i.pinimg.com/736x/0f/c6/1d/0fc61dfba6f931d0fb58f8d4bd48c659.jpg',  # Доктор Живаго
            'https://i.pinimg.com/736x/3e/ee/8f/3eee8f1fb94f53dfcfa0dd7538741931.jpg',  # Собачье сердце
            'https://i.pinimg.com/736x/3a/f7/98/3af79860825a293ae30f688e9871c14d.jpg',  # Братья Карамазовы
            'https://i.pinimg.com/736x/7c/41/01/7c41014eaa020658d2e6099c827b2368.jpg',  # Мертвые души
            'https://i.pinimg.com/736x/27/a9/d3/27a9d37de038b5027a067190c5a07cc6.jpg',  # Гарри Поттер и философский камень
            'https://i.pinimg.com/1200x/c6/a7/e1/c6a7e1a2a12fe38a112528e99e4dc82c.jpg',  # Маленький принц
            'https://i.pinimg.com/1200x/81/6e/93/816e939a102dcc50dc91e332cb04f574.jpg',  # Алиса в Стране чудес
            'https://i.pinimg.com/736x/ef/99/98/ef999826ad60652c392b934f5aed9733.jpg',  # Винни-Пух
            'https://imo10.labirint.ru/books/914243/ph_001.jpg/242-0',  # Карлсон, который живет на крыше
            'https://i.pinimg.com/1200x/cd/2d/fb/cd2dfbc08fdf99ab11d3e94e2691c7e4.jpg',  # Приключения Тома Сойера
            'https://i.pinimg.com/736x/a1/28/ba/a128ba9943e98075336f1204d3517fd9.jpg',  # Питер Пэн
            'https://vilkibooks.com/wp-content/uploads/2019/11/IMG_7308-scaled.jpg',  # Чарли и шоколадная фабрика
            'https://i.pinimg.com/1200x/28/b5/c8/28b5c8f2c3fd79bee65a293daf8b3ec1.jpg',  # Хроники Нарнии
            'https://i.pinimg.com/736x/82/62/99/82629959c01ecc444c5c9cea73d9265a.jpg',  # Гарри Поттер и Тайная комната
            'https://img.labirint.ru/images/comments_pic/1914/0_ffc3c45efea067abcd8184c5fe76cd37_1554471870.jpg',  # Краткая история времени
            'https://avatars.mds.yandex.net/get-mpic/18243071/2a0000019bb89c8fdafc6c4ae4d36f594d7b/orig',  # Космос
            'https://lh4.googleusercontent.com/proxy/UQyjvYamrbe9BEsN6Gnsqd311FbPXjCGPKYSn3KlYsm8F7d6E2iwdMTbPR2Gmq8lyoQs_Oxfa0Bxim2Njt8Epn6I8G8',  # Эгоистичный ген
            'https://shvk.store/wp-content/uploads/2019/02/30_darvin.jpg',  # Происхождение видов
            'https://i.pinimg.com/736x/47/57/8c/47578c075063185876e1f3a3e88344b9.jpg',  # Теория относительности
            'https://i.pinimg.com/736x/9e/0c/93/9e0c9337c65b26c58d09118f2b9f683f.jpg',  # Самоучитель Python
            'https://storage.yandexcloud.net/prod-file-public/6a67/4172/9a58/bf19c2dd-6a67-4172-9a58-d48d623691a2-resized.webp',  # Математика. 10 класс
            'https://storage.yandexcloud.net/prod-file-public/9988/48ba/90ce/4bee8631-9988-48ba-90ce-685bad61c272-resized.webp',  # Физика. 11 класс
            'https://ir.ozone.ru/s3/multimedia-j/6171700831.jpg',  # Английский язык. Грамматика
            'https://storage.yandexcloud.net/prod-file-public/960a/462d/9e33/f6c3dec7-960a-462d-9e33-b98d56d127e7-resized.webp',  # История России. 9 класс
            'https://i.pinimg.com/1200x/f9/29/4e/f9294e433eea8e60efb8442af699a054.jpg',  # Богатый папа, бедный папа
            'https://i.pinimg.com/736x/14/1e/f4/141ef4d95d24baf46e2ad0c21beb8ea3.jpg',  # 7 навыков высокоэффективных людей
            'https://i.pinimg.com/736x/1a/28/a7/1a28a7f6a12abd4a1c7a7e3cfa3cdea3.jpg',  # Думай и богатей
            'https://i.pinimg.com/1200x/69/24/1b/69241b877cd5602734c1e43121e5b3e0.jpg',  # Как завоевать друзей
            'https://i.pinimg.com/736x/d0/a8/98/d0a898bc2ae5b7d3743b1f92ff5f07cf.jpg',  # Стартап
        ]
        
        # Канцтовары
        office_images = [
            'https://i.pinimg.com/1200x/1f/0e/c4/1f0ec47997fc213c767119794a6062b5.jpg',  # Ручка шариковая синяя
            'https://i.pinimg.com/1200x/73/06/43/73064397e574583306c0d4e07c86cbd0.jpg',  # Ручка гелевая черная
            'https://i.pinimg.com/736x/3d/d8/c0/3dd8c0b36a34c71d060dca120315c883.jpg',  # Карандаш простой HB
            'https://i.pinimg.com/736x/fb/ba/9b/fbba9bd58af72811ca728e2a44ea018b.jpg',  # Набор цветных карандашей 12 шт
            'https://i.pinimg.com/736x/09/34/08/09340804d08720f8186420f2da60bd7b.jpg',  # Ручка перьевая
            'https://i.pinimg.com/736x/5e/f7/d5/5ef7d5780dd0118ae85471496ebe560a.jpg',  # Тетрадь 48 листов, клетка
            'https://i.pinimg.com/736x/88/db/6c/88db6cd30484bc7342db1387756f75eb.jpg',  # Тетрадь 96 листов, линейка
            'https://i.pinimg.com/1200x/ec/f2/41/ecf2419120f762a54e455f180f8b1f78.jpg',  # Блокнот А5, 80 листов
            'https://i.pinimg.com/1200x/09/0f/26/090f2635df4b1393e322507a7af3fe51.jpg',  # Ежедневник 2026
            'https://i.pinimg.com/736x/e5/08/50/e50850d2c8cb763951734b22c170ee67.jpg',  # Записная книжка
            'https://i.pinimg.com/736x/c5/bf/75/c5bf752f33e86f4bae7dce0e166b58e9.jpg',  # Папка-файл А4, 20 файлов
            'https://i.pinimg.com/1200x/46/f5/5d/46f55dbb92882669fbb9c789eba4bc41.jpg',  # Папка-скоросшиватель
            'https://images.satu.kz/139936861_w1280_h640_139936861.jpg',  # Файлы А4, 100 шт
            'https://i.pinimg.com/736x/18/eb/21/18eb210b1306637b517b1c956e5e3204.jpg',  # Степлер малый
            'https://i.pinimg.com/736x/18/e4/ac/18e4acf3be732007308f5ead56d561a8.jpg',  # Дырокол офисный
            'https://i.pinimg.com/1200x/32/5c/14/325c14137a5a794349f8b209003ef99e.jpg',  # Калькулятор настольный
            'https://i.pinimg.com/736x/ed/e2/9f/ede29f43a7aca4aab8a85e2addad9fb4.jpg',  # Линейка 30 см
            'https://i.pinimg.com/736x/63/ad/29/63ad29ba3a119979b7e2041ff63b37c4.jpg',  # Ножницы офисные
            'https://images.firma-gamma.ru/images/9/2/d14207584962l.jpg',  # Клей-карандаш
            'https://optstroy-lider.ru/image/cache/catalog/product-new/image/catalog/29171111-600x600.jpg',  # Скотч прозрачный
            'https://i.pinimg.com/736x/c0/21/7d/c0217dfa9b53e768264ebfdb0c16c6af.jpg',  # Корректор
        ]
        
        # Подарочные издания
        gift_images = [
            'https://ir.ozone.ru/s3/multimedia-q/c1000/6821859446.jpg',  # Собрание сочинений Пушкина
            'https://ir.ozone.ru/s3/multimedia-2/c1000/6078266522.jpg',  # Великие художники. Альбом
            'https://printonline.ru/upload/resize_cache/iblock/ebe/400_400_1/e0yf0f6yr5tgr6shcwbvrtgkmow6slc8.jpg',  # Подарочный набор ручек
            'https://roossa.ru/wp-content/uploads/2025/11/img_2606.jpg',  # Энциклопедия в кожаном переплете
            'https://i.pinimg.com/1200x/e0/c4/ba/e0c4bac2227d10714d64be1e9dd64f99.jpg',  # Подарочный набор канцтоваров
        ]
        
        products_data = [
            # Художественная литература (15 книг)
            {'article': 'BOOK-001', 'name': 'Война и мир', 'description': 'Роман-эпопея Льва Толстого в 4 томах', 'price': 1500.00, 'stock': 25, 'category': book_subcategory_objects[0], 'image': book_images[0]},
            {'article': 'BOOK-002', 'name': 'Преступление и наказание', 'description': 'Роман Федора Достоевского', 'price': 450.00, 'stock': 30, 'category': book_subcategory_objects[0], 'image': book_images[1]},
            {'article': 'BOOK-003', 'name': 'Мастер и Маргарита', 'description': 'Роман Михаила Булгакова', 'price': 550.00, 'stock': 20, 'category': book_subcategory_objects[0], 'image': book_images[2]},
            {'article': 'BOOK-004', 'name': '1984', 'description': 'Антиутопический роман Джорджа Оруэлла', 'price': 480.00, 'stock': 15, 'category': book_subcategory_objects[0], 'image': book_images[3]},
            {'article': 'BOOK-005', 'name': 'Анна Каренина', 'description': 'Роман Льва Толстого', 'price': 600.00, 'stock': 18, 'category': book_subcategory_objects[0], 'image': book_images[4]},
            {'article': 'BOOK-006', 'name': 'Идиот', 'description': 'Роман Федора Достоевского', 'price': 500.00, 'stock': 22, 'category': book_subcategory_objects[0], 'image': book_images[5]},
            {'article': 'BOOK-007', 'name': 'Отцы и дети', 'description': 'Роман Ивана Тургенева', 'price': 380.00, 'stock': 28, 'category': book_subcategory_objects[0], 'image': book_images[6]},
            {'article': 'BOOK-008', 'name': 'Евгений Онегин', 'description': 'Роман в стихах Александра Пушкина', 'price': 350.00, 'stock': 35, 'category': book_subcategory_objects[0], 'image': book_images[7]},
            {'article': 'BOOK-009', 'name': 'Обломов', 'description': 'Роман Ивана Гончарова', 'price': 420.00, 'stock': 20, 'category': book_subcategory_objects[0], 'image': book_images[8]},
            {'article': 'BOOK-010', 'name': 'Герой нашего времени', 'description': 'Роман Михаила Лермонтова', 'price': 400.00, 'stock': 25, 'category': book_subcategory_objects[0], 'image': book_images[9]},
            {'article': 'BOOK-011', 'name': 'Тихий Дон', 'description': 'Роман-эпопея Михаила Шолохова', 'price': 800.00, 'stock': 15, 'category': book_subcategory_objects[0], 'image': book_images[10]},
            {'article': 'BOOK-012', 'name': 'Доктор Живаго', 'description': 'Роман Бориса Пастернака', 'price': 650.00, 'stock': 12, 'category': book_subcategory_objects[0], 'image': book_images[11]},
            {'article': 'BOOK-013', 'name': 'Собачье сердце', 'description': 'Повесть Михаила Булгакова', 'price': 320.00, 'stock': 30, 'category': book_subcategory_objects[0], 'image': book_images[12]},
            {'article': 'BOOK-014', 'name': 'Братья Карамазовы', 'description': 'Роман Федора Достоевского', 'price': 750.00, 'stock': 10, 'category': book_subcategory_objects[0], 'image': book_images[13]},
            {'article': 'BOOK-015', 'name': 'Мертвые души', 'description': 'Поэма Николая Гоголя', 'price': 450.00, 'stock': 20, 'category': book_subcategory_objects[0], 'image': book_images[14]},
            
            # Детская литература (10 книг)
            {'article': 'BOOK-016', 'name': 'Гарри Поттер и философский камень', 'description': 'Первая книга серии о Гарри Поттере', 'price': 650.00, 'stock': 40, 'category': book_subcategory_objects[1], 'image': book_images[15]},
            {'article': 'BOOK-017', 'name': 'Маленький принц', 'description': 'Философская сказка Антуана де Сент-Экзюпери', 'price': 320.00, 'stock': 35, 'category': book_subcategory_objects[1], 'image': book_images[16]},
            {'article': 'BOOK-018', 'name': 'Алиса в Стране чудес', 'description': 'Сказка Льюиса Кэрролла', 'price': 380.00, 'stock': 28, 'category': book_subcategory_objects[1], 'image': book_images[17]},
            {'article': 'BOOK-019', 'name': 'Винни-Пух', 'description': 'Сказка Алана Милна', 'price': 450.00, 'stock': 32, 'category': book_subcategory_objects[1], 'image': book_images[18]},
            {'article': 'BOOK-020', 'name': 'Карлсон, который живет на крыше', 'description': 'Повесть Астрид Линдгрен', 'price': 400.00, 'stock': 30, 'category': book_subcategory_objects[1], 'image': book_images[19]},
            {'article': 'BOOK-021', 'name': 'Приключения Тома Сойера', 'description': 'Роман Марка Твена', 'price': 420.00, 'stock': 25, 'category': book_subcategory_objects[1], 'image': book_images[20]},
            {'article': 'BOOK-022', 'name': 'Питер Пэн', 'description': 'Сказка Джеймса Барри', 'price': 380.00, 'stock': 22, 'category': book_subcategory_objects[1], 'image': book_images[21]},
            {'article': 'BOOK-023', 'name': 'Чарли и шоколадная фабрика', 'description': 'Повесть Роальда Даля', 'price': 450.00, 'stock': 28, 'category': book_subcategory_objects[1], 'image': book_images[22]},
            {'article': 'BOOK-024', 'name': 'Хроники Нарнии', 'description': 'Фэнтезийный цикл Клайва Льюиса', 'price': 1200.00, 'stock': 15, 'category': book_subcategory_objects[1], 'image': book_images[23]},
            {'article': 'BOOK-025', 'name': 'Гарри Поттер и Тайная комната', 'description': 'Вторая книга серии о Гарри Поттере', 'price': 650.00, 'stock': 38, 'category': book_subcategory_objects[1], 'image': book_images[24]},
            
            # Научная литература (5 книг)
            {'article': 'BOOK-026', 'name': 'Краткая история времени', 'description': 'Научно-популярная книга Стивена Хокинга', 'price': 720.00, 'stock': 12, 'category': book_subcategory_objects[2], 'image': book_images[25]},
            {'article': 'BOOK-027', 'name': 'Космос', 'description': 'Книга Карла Сагана о Вселенной', 'price': 850.00, 'stock': 10, 'category': book_subcategory_objects[2], 'image': book_images[26]},
            {'article': 'BOOK-028', 'name': 'Эгоистичный ген', 'description': 'Книга Ричарда Докинза', 'price': 680.00, 'stock': 14, 'category': book_subcategory_objects[2], 'image': book_images[27]},
            {'article': 'BOOK-029', 'name': 'Происхождение видов', 'description': 'Труд Чарльза Дарвина', 'price': 950.00, 'stock': 8, 'category': book_subcategory_objects[2], 'image': book_images[28]},
            {'article': 'BOOK-030', 'name': 'Теория относительности', 'description': 'Популярное изложение теории Эйнштейна', 'price': 780.00, 'stock': 11, 'category': book_subcategory_objects[2], 'image': book_images[29]},
            
            # Учебники и пособия (5 книг)
            {'article': 'BOOK-031', 'name': 'Самоучитель Python', 'description': 'Учебное пособие по программированию на Python', 'price': 890.00, 'stock': 18, 'category': book_subcategory_objects[3], 'image': book_images[30]},
            {'article': 'BOOK-032', 'name': 'Математика. 10 класс', 'description': 'Учебник по алгебре и геометрии', 'price': 650.00, 'stock': 22, 'category': book_subcategory_objects[3], 'image': book_images[31]},
            {'article': 'BOOK-033', 'name': 'Физика. 11 класс', 'description': 'Учебник по физике для старших классов', 'price': 720.00, 'stock': 20, 'category': book_subcategory_objects[3], 'image': book_images[32]},
            {'article': 'BOOK-034', 'name': 'Английский язык. Грамматика', 'description': 'Справочник по английской грамматике', 'price': 580.00, 'stock': 25, 'category': book_subcategory_objects[3], 'image': book_images[33]},
            {'article': 'BOOK-035', 'name': 'История России. 9 класс', 'description': 'Учебник по истории России', 'price': 600.00, 'stock': 19, 'category': book_subcategory_objects[3], 'image': book_images[34]},
            
            # Бизнес-литература (5 книг)
            {'article': 'BOOK-036', 'name': 'Богатый папа, бедный папа', 'description': 'Книга Роберта Кийосаки о финансовой грамотности', 'price': 580.00, 'stock': 16, 'category': book_subcategory_objects[4], 'image': book_images[35]},
            {'article': 'BOOK-037', 'name': '7 навыков высокоэффективных людей', 'description': 'Бизнес-книга Стивена Кови', 'price': 620.00, 'stock': 14, 'category': book_subcategory_objects[4], 'image': book_images[36]},
            {'article': 'BOOK-038', 'name': 'Думай и богатей', 'description': 'Классическая книга Наполеона Хилла', 'price': 550.00, 'stock': 20, 'category': book_subcategory_objects[4], 'image': book_images[37]},
            {'article': 'BOOK-039', 'name': 'Как завоевать друзей', 'description': 'Книга Дейла Карнеги', 'price': 480.00, 'stock': 24, 'category': book_subcategory_objects[4], 'image': book_images[38]},
            {'article': 'BOOK-040', 'name': 'Стартап', 'description': 'Книга Гая Кавасаки о предпринимательстве', 'price': 650.00, 'stock': 15, 'category': book_subcategory_objects[4], 'image': book_images[39]},
            
            # Канцтовары - Ручки и карандаши (5 товаров)
            {'article': 'PEN-001', 'name': 'Ручка шариковая синяя', 'description': 'Шариковая ручка с синими чернилами, 0.7 мм', 'price': 25.00, 'stock': 150, 'category': office_subcategory_objects[0], 'image': office_images[0]},
            {'article': 'PEN-002', 'name': 'Ручка гелевая черная', 'description': 'Гелевая ручка с черными чернилами, 0.5 мм', 'price': 35.00, 'stock': 120, 'category': office_subcategory_objects[0], 'image': office_images[1]},
            {'article': 'PEN-003', 'name': 'Карандаш простой HB', 'description': 'Простой карандаш средней твердости', 'price': 15.00, 'stock': 200, 'category': office_subcategory_objects[0], 'image': office_images[2]},
            {'article': 'PEN-004', 'name': 'Набор цветных карандашей 12 шт', 'description': 'Набор цветных карандашей в картонной упаковке', 'price': 180.00, 'stock': 45, 'category': office_subcategory_objects[0], 'image': office_images[3]},
            {'article': 'PEN-005', 'name': 'Ручка перьевая', 'description': 'Перьевая ручка с чернилами', 'price': 450.00, 'stock': 30, 'category': office_subcategory_objects[0], 'image': office_images[4]},
            
            # Канцтовары - Тетради и блокноты (5 товаров)
            {'article': 'NOTE-001', 'name': 'Тетрадь 48 листов, клетка', 'description': 'Тетрадь в клетку, 48 листов, обложка картон', 'price': 45.00, 'stock': 100, 'category': office_subcategory_objects[1], 'image': office_images[5]},
            {'article': 'NOTE-002', 'name': 'Тетрадь 96 листов, линейка', 'description': 'Тетрадь в линейку, 96 листов, обложка картон', 'price': 75.00, 'stock': 80, 'category': office_subcategory_objects[1], 'image': office_images[6]},
            {'article': 'NOTE-003', 'name': 'Блокнот А5, 80 листов', 'description': 'Блокнот формата А5, 80 листов, твердая обложка', 'price': 120.00, 'stock': 60, 'category': office_subcategory_objects[1], 'image': office_images[7]},
            {'article': 'NOTE-004', 'name': 'Ежедневник 2026', 'description': 'Ежедневник на 2026 год, формат А5', 'price': 350.00, 'stock': 30, 'category': office_subcategory_objects[1], 'image': office_images[8]},
            {'article': 'NOTE-005', 'name': 'Записная книжка', 'description': 'Небольшая записная книжка в кожаном переплете', 'price': 280.00, 'stock': 25, 'category': office_subcategory_objects[1], 'image': office_images[9]},
            
            # Канцтовары - Папки и файлы (3 товара)
            {'article': 'FOLDER-001', 'name': 'Папка-файл А4, 20 файлов', 'description': 'Папка-файл с 20 прозрачными файлами', 'price': 95.00, 'stock': 70, 'category': office_subcategory_objects[2], 'image': office_images[10]},
            {'article': 'FOLDER-002', 'name': 'Папка-скоросшиватель', 'description': 'Папка-скоросшиватель А4, синяя', 'price': 55.00, 'stock': 90, 'category': office_subcategory_objects[2], 'image': office_images[11]},
            {'article': 'FOLDER-003', 'name': 'Файлы А4, 100 шт', 'description': 'Прозрачные файлы формата А4, упаковка 100 шт', 'price': 280.00, 'stock': 50, 'category': office_subcategory_objects[2], 'image': office_images[12]},
            
            # Канцтовары - Офисные принадлежности (8 товаров)
            {'article': 'OFFICE-001', 'name': 'Степлер малый', 'description': 'Степлер на 20 скрепок', 'price': 150.00, 'stock': 40, 'category': office_subcategory_objects[3], 'image': office_images[13]},
            {'article': 'OFFICE-002', 'name': 'Дырокол офисный', 'description': 'Дырокол на 2 отверстия', 'price': 220.00, 'stock': 35, 'category': office_subcategory_objects[3], 'image': office_images[14]},
            {'article': 'OFFICE-003', 'name': 'Калькулятор настольный', 'description': 'Настольный калькулятор с большим дисплеем', 'price': 450.00, 'stock': 25, 'category': office_subcategory_objects[3], 'image': office_images[15]},
            {'article': 'OFFICE-004', 'name': 'Линейка 30 см', 'description': 'Пластиковая линейка 30 см', 'price': 30.00, 'stock': 110, 'category': office_subcategory_objects[3], 'image': office_images[16]},
            {'article': 'OFFICE-005', 'name': 'Ножницы офисные', 'description': 'Офисные ножницы 20 см', 'price': 120.00, 'stock': 50, 'category': office_subcategory_objects[3], 'image': office_images[17]},
            {'article': 'OFFICE-006', 'name': 'Клей-карандаш', 'description': 'Клей-карандаш 20г', 'price': 45.00, 'stock': 80, 'category': office_subcategory_objects[3], 'image': office_images[18]},
            {'article': 'OFFICE-007', 'name': 'Скотч прозрачный', 'description': 'Скотч прозрачный 19мм, 33м', 'price': 55.00, 'stock': 90, 'category': office_subcategory_objects[3], 'image': office_images[19]},
            {'article': 'OFFICE-008', 'name': 'Корректор', 'description': 'Корректор-ручка белый', 'price': 65.00, 'stock': 60, 'category': office_subcategory_objects[3], 'image': office_images[20]},

            # Подарочные издания (дополнительно 5 товаров)
            {'article': 'GIFT-001', 'name': 'Собрание сочинений Пушкина', 'description': 'Подарочное издание в кожаном переплете, 5 томов', 'price': 3500.00, 'stock': 8, 'category': main_categories[2], 'image': gift_images[0]},
            {'article': 'GIFT-002', 'name': 'Великие художники. Альбом', 'description': 'Подарочный альбом с репродукциями картин', 'price': 2800.00, 'stock': 5, 'category': main_categories[2], 'image': gift_images[1]},
            {'article': 'GIFT-003', 'name': 'Подарочный набор ручек', 'description': 'Набор подарочных ручек в футляре', 'price': 1200.00, 'stock': 12, 'category': main_categories[2], 'image': gift_images[2]},
            {'article': 'GIFT-004', 'name': 'Энциклопедия в кожаном переплете', 'description': 'Подарочная энциклопедия в кожаном переплете', 'price': 4500.00, 'stock': 6, 'category': main_categories[2], 'image': gift_images[3]},
            {'article': 'GIFT-005', 'name': 'Подарочный набор канцтоваров', 'description': 'Набор премиум канцтоваров в подарочной упаковке', 'price': 2500.00, 'stock': 10, 'category': main_categories[2], 'image': gift_images[4]},
        ]
        
        products = []
        for prod_data in products_data:
            # Проверяем, существует ли товар
            if not Product.query.filter_by(article=prod_data['article']).first():
                category = prod_data['category']
                
                product = Product(
                    article=prod_data['article'],
                    name=prod_data['name'],
                    description=prod_data['description'],
                    price=Decimal(str(prod_data['price'])),
                    stock_quantity=prod_data['stock'],
                    image_url=prod_data.get('image', ''),
                    category_id=category.id
                )
                db.session.add(product)
                products.append(product)
        
        db.session.commit()
        print(f"Создано товаров: {len(products)}")
        
        # ==================== 4. Создание корзин и заказов ====================
        print("Создание корзин и заказов...")
        
        # Создаем корзины для некоторых пользователей
        for i, user in enumerate(users[:3]):  # Для первых 3 пользователей
            cart = Cart.query.filter_by(user_id=user.id).first()
            if not cart:
                cart = Cart(user_id=user.id)
                db.session.add(cart)
                db.session.flush()
                
                # Добавляем товары в корзину
                num_items = random.randint(1, 3)
                selected_products = random.sample(products, min(num_items, len(products)))
                
                for product in selected_products:
                    if product.stock_quantity > 0:
                        quantity = random.randint(1, min(3, product.stock_quantity))
                        cart_item = CartItem(
                            cart_id=cart.id,
                            product_id=product.id,
                            quantity=quantity,
                            price_at_add=product.price
                        )
                        db.session.add(cart_item)
        
        db.session.commit()
        print("Создано корзин: 3")
        
        # Создаем несколько заказов
        order_statuses = ['pending', 'processing', 'shipped', 'delivered']
        
        for i, user in enumerate(users[:3]):  # Для первых 3 пользователей
            num_orders = random.randint(1, 2)
            
            for j in range(num_orders):
                # Выбираем случайные товары
                num_items = random.randint(1, 4)
                selected_products = random.sample(products, min(num_items, len(products)))
                
                # Вычисляем общую сумму
                total_amount = Decimal('0')
                order_items_data = []
                
                for product in selected_products:
                    if product.stock_quantity > 0:
                        quantity = random.randint(1, min(2, product.stock_quantity))
                        price = product.price
                        total_amount += price * quantity
                        order_items_data.append({
                            'product': product,
                            'quantity': quantity,
                            'price': price
                        })
                
                if order_items_data:
                    # Создаем заказ
                    order = Order(
                        user_id=user.id,
                        status=random.choice(order_statuses),
                        total_amount=total_amount,
                        created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                    )
                    db.session.add(order)
                    db.session.flush()
                    
                    # Создаем позиции заказа
                    for item_data in order_items_data:
                        order_item = OrderItem(
                            order_id=order.id,
                            product_id=item_data['product'].id,
                            quantity=item_data['quantity'],
                            price_per_unit=item_data['price']
                        )
                        db.session.add(order_item)
        
        db.session.commit()
        orders_count = Order.query.count()
        print(f"Создано заказов: {orders_count}")
        
        print("\n" + "="*50)
        print("База данных успешно заполнена!")
        print("="*50)
        print("\nУчетные данные для входа:")
        print("Администратор (создается автоматически):")
        print("  Email: admin@planeta.ru")
        print("  Пароль: admin123")
        print("\nПользователи:")
        print("  Email: ivanov@example.com")
        print("  Пароль: user123")
        print("  (и другие пользователи с паролем: user123)")
        print("\n" + "="*50)

if __name__ == '__main__':
    fill_database()
