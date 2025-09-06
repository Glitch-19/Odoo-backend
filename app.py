import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from flask_cors import CORS

# ----------------------
# Configuration
# ----------------------
app = Flask(__name__)
CORS(app)

# Read DATABASE_URL from environment; fallback to sqlite for quick local dev
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///ecofinds_dev.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'change-this-secret')
# JWT expiry (example: 1 hour)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# ----------------------
# Models
# ----------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='owner', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)

    products = db.relationship('Product', backref='category', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(255), default='https://via.placeholder.com/300')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'category_id': self.category_id,
            'price': float(self.price),
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class CartItem(db.Model):
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product': self.product.to_dict() if self.product else None,
            'quantity': self.quantity,
            'added_at': self.added_at.isoformat()
        }

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    items = db.relationship('OrderItem', backref='order', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'order_date': self.order_date.isoformat(),
            'total_amount': float(self.total_amount),
            'items': [item.to_dict() for item in self.items]
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10,2), nullable=False)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'product': self.product.to_dict() if self.product else None,
            'quantity': self.quantity,
            'price': float(self.price)
        }

class SearchKeyword(db.Model):
    __tablename__ = 'search_keywords'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    keyword = db.Column(db.String(100), nullable=False)
    searched_at = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------------
# Authentication routes
#removebelow
@app.route('/api/debug/users', methods=['GET'])
def debug_list_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])
# ----------------------
@app.route("/")
def home():
    return "Hello, World!"
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not (username and email and password):
        return jsonify({'message': 'username, email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already registered'}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    return jsonify({'message': 'User registered', 'access_token': access_token, 'user': user.to_dict()}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not (email and password):
        return jsonify({'message': 'email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({'message': 'Login successful', 'access_token': access_token, 'user': user.to_dict()})

# ----------------------
# User profile
# ----------------------
@app.route('/api/users/me', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@app.route('/api/users/me', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if username:
        user.username = username
    if email:
        # optional: check email uniqueness
        existing = User.query.filter(User.email==email, User.id!=user.id).first()
        if existing:
            return jsonify({'message': 'Email already in use'}), 400
        user.email = email
    if password:
        user.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'user': user.to_dict()})

# ----------------------
# Categories
# ----------------------
@app.route('/api/categories', methods=['GET'])
def list_categories():
    cats = Category.query.order_by(Category.name).all()
    return jsonify([c.to_dict() for c in cats])

# Development helper: seed categories (not protected)
@app.route('/api/seed_categories', methods=['POST'])
def seed_categories():
    names = request.json.get('names', [])
    created = []
    for n in names:
        if not Category.query.filter_by(name=n).first():
            c = Category(name=n)
            db.session.add(c)
            created.append(n)
    db.session.commit()
    return jsonify({'created': created})

# ----------------------
# Products (CRUD) with filtering & search & pagination
# ----------------------
@app.route('/api/products', methods=['GET'])
def get_products():
    # query params: category, keyword, page, per_page
    category = request.args.get('category')
    keyword = request.args.get('keyword')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    q = Product.query
    if category:
        # allow either category id or name
        if category.isdigit():
            q = q.filter(Product.category_id == int(category))
        else:
            q = q.join(Category).filter(Category.name.ilike(f"%{category}%"))
    if keyword:
        q = q.filter(Product.title.ilike(f"%{keyword}%"))
        # store keyword for analytics (optional)
        kw = SearchKeyword(keyword=keyword)
        db.session.add(kw)
        db.session.commit()

    pag = q.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = [p.to_dict() for p in pag.items]
    return jsonify({
        'items': items,
        'total': pag.total,
        'page': pag.page,
        'per_page': pag.per_page,
        'pages': pag.pages
    })

@app.route('/api/products', methods=['POST'])
@jwt_required()
def create_product():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    required = ['title', 'category_id', 'price']
    for f in required:
        if f not in data:
            return jsonify({'message': f'{f} is required'}), 400

    product = Product(
        user_id=user_id,
        title=data['title'],
        description=data.get('description', ''),
        category_id=data['category_id'],
        price=data['price'],
        image_url=data.get('image_url', 'https://via.placeholder.com/300')
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product created', 'product': product.to_dict()}), 201

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    p = Product.query.get_or_404(product_id)
    return jsonify(p.to_dict())

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    user_id = get_jwt_identity()
    p = Product.query.get_or_404(product_id)
    if p.user_id != user_id:
        return jsonify({'message': 'Forbidden: you do not own this product'}), 403
    data = request.get_json() or {}
    p.title = data.get('title', p.title)
    p.description = data.get('description', p.description)
    p.category_id = data.get('category_id', p.category_id)
    p.price = data.get('price', p.price)
    p.image_url = data.get('image_url', p.image_url)
    db.session.commit()
    return jsonify({'message': 'Product updated', 'product': p.to_dict()})

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    user_id = get_jwt_identity()
    p = Product.query.get_or_404(product_id)
    if p.user_id != user_id:
        return jsonify({'message': 'Forbidden: you do not own this product'}), 403
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Product deleted'})

# ----------------------
# Cart
# ----------------------
@app.route('/api/cart', methods=['GET'])
@jwt_required()
def get_cart():
    user_id = get_jwt_identity()
    items = CartItem.query.filter_by(user_id=user_id).all()
    return jsonify([it.to_dict() for it in items])

@app.route('/api/cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))
    if not product_id:
        return jsonify({'message': 'product_id required'}), 400
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'message': 'Product not found'}), 404

    existing = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing:
        existing.quantity = existing.quantity + quantity
    else:
        existing = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        db.session.add(existing)
    db.session.commit()
    return jsonify({'message': 'Added to cart', 'cart_item': existing.to_dict()})

@app.route('/api/cart/<int:item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(item_id):
    user_id = get_jwt_identity()
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != user_id:
        return jsonify({'message': 'Forbidden'}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Item removed from cart'})

# ----------------------
# Orders / Checkout
# ----------------------
@app.route('/api/orders', methods=['POST'])
@jwt_required()
def create_order():
    user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return jsonify({'message': 'Cart is empty'}), 400

    try:
        order = Order(user_id=user_id, order_date=datetime.utcnow(), total_amount=0)
        db.session.add(order)
        total = 0
        db.session.flush()  # get order.id

        for ci in cart_items:
            product = Product.query.get(ci.product_id)
            price = float(product.price)
            oi = OrderItem(order_id=order.id, product_id=product.id, quantity=ci.quantity, price=price)
            db.session.add(oi)
            total += price * ci.quantity
            db.session.delete(ci)  # clear cart

        order.total_amount = total
        db.session.commit()
        return jsonify({'message': 'Order created', 'order': order.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error creating order', 'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
@jwt_required()
def list_orders():
    user_id = get_jwt_identity()
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.order_date.desc()).all()
    return jsonify([o.to_dict() for o in orders])

# ----------------------
# Run server
# ----------------------
if __name__ == '__main__':
    # For quick local dev: create DB tables if they don't exist
    if 'sqlite' in DATABASE_URL and not os.path.exists(DATABASE_URL.replace('sqlite:///', '')):
        with app.app_context():
            db.create_all()
            print('SQLite DB created (dev)')

    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG', '1') == '1')
