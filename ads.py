import flask
import pydantic
from flask import request, jsonify
from flask.views import MethodView
from flask_bcrypt import Bcrypt
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    String,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = flask.Flask('ads')
bcrypt = Bcrypt(app)
PG_DSN = os.getenv('PG_DSN')
SMS_TOKEN = os.getenv('SMS_TOKEN')
engine = create_engine(PG_DSN)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class UserModel(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_name = Column(String(100), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    registration_time = Column(DateTime, server_default=func.now())
    phone_num = Column(String(20), nullable=False, unique=True)

    def to_dict(self):
        return {
            'user_name': self.user_name,
            'registration_time': int(self.registration_time.timestamp()),
            'id': self.id,
            'phone_num': self.phone_num,
        }

    def check_password(self, password: str):
        return bcrypt.check_password_hash(self.password.encode(), password.encode())


class Token(Base):
    __tablename__ = 'tokens'
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    creation_time = Column(DateTime, server_default=func.now())
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(UserModel, lazy='joined')


class SmsModel(Base):
    __tablename__ = "sms"
    id = Column(Integer, primary_key=True)
    income_sms = Column(String(144), nullable=True, unique=False)
    creation_time = Column(DateTime, server_default=func.now())
    outcome_sms = Column(String(144), nullable=True, unique=False)
    status_time = Column(DateTime)
    status = Column(Integer, nullable=False, unique=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(UserModel, lazy='joined')

    def to_dict(self):
        return {
            'income_sms': self.income_sms,
            'creation_time': int(self.creation_time.timestamp()),
            'outcome_sms': self.outcome_sms,
            'status_time': int(self.status_time.timestamp()),
            'status': self.status,
            'id': self.id,
            'user_id': self.user_id
        }


Base.metadata.create_all(engine)


class CreateUserValidation(pydantic.BaseModel):
    user_name: str
    password: str
    phone_num: str

    @pydantic.validator('password')
    def strong_password(cls, value):
        if len(value) < 5:
            raise ValueError('too easy')
        return value


class HTTPError(Exception):
    def __init__(self, status_code: int, message):
        self.status_code = status_code
        self.message = message


@app.errorhandler(HTTPError)
def error_handle(error):
    response = jsonify({"message": error.message})
    response.status_code = error.status_code
    return response


def check_token(session):
    token = (session.query(Token).filter(Token.id == request.headers.get('token')).first())
    if token is None:
        raise HTTPError(401, 'invalid token')
    return token


class AllUserView(MethodView):
    def get(self):
        users = []
        with Session() as session:
            for item in session.query(UserModel):
                users.append(item.to_dict())
        return flask.jsonify({'users': users})


class UserView(MethodView):
    def get(self, user_id: int):
        with Session() as session:
            token = check_token(session)
            if token.user.id != user_id:
                raise HTTPError(403, "auth error")
            return jsonify(token.user.to_dict())

    def post(self):
        try:
            validated_data = CreateUserValidation(**request.json).dict()
        except pydantic.ValidationError as err:
            raise HTTPError(400, err.errors())
        with Session() as session:
            validated_data['password'] = bcrypt.generate_password_hash(validated_data['password'].encode()).decode()
            new_user = UserModel(**validated_data)
            session.add(new_user)
            try:
                session.commit()
                return flask.jsonify(new_user.to_dict())
            except IntegrityError:
                user_name = validated_data['user_name']
                session.rollback()
                return flask.jsonify({'error': f'Username {user_name} already exists'})


@app.route("/")
def hello():
    return "<h1 style='color:blue'>Ocean inside: Weather</h1>"


@app.route('/login/', methods=['POST'])
def login():
    login_data = request.json
    with Session() as session:
        user = (
            session.query(UserModel)
            .filter(UserModel.user_name == login_data['user_name'])
            .first()
        )
        if user is None or not user.check_password(login_data['password']):
            raise HTTPError(401, 'incorrect user or password')
        token = Token(user_id=user.id)
        session.add(token)
        session.commit()
        return jsonify({'token': token.id})


class AllSmsView(MethodView):
    def get(self):
        sms_token = request.headers.get('token')
        if sms_token == SMS_TOKEN:
            sms = []
            with Session() as session:
                for item in session.query(SmsModel):
                    sms.append(item.to_dict())
            return flask.jsonify({'sms': sms})
        else:
            raise HTTPError(403, 'no permission')


class SmsView(MethodView):
    def get(self, sms_id: int):
        sms_token = request.headers.get('token')
        if sms_token == SMS_TOKEN:
            with Session() as session:
                sms = session.query(SmsModel).filter(SmsModel.id == sms_id).first()
                return flask.jsonify(sms.to_dict())
        else:
            raise HTTPError(403, 'no permission')

    def post(self):
        sms_token = request.headers.get('token')
        if sms_token == SMS_TOKEN:
            new_sms_data = request.json
            with Session() as session:
                user = session.query(UserModel).filter(UserModel.phone_num == new_sms_data['phone_num']).first()
                if user:
                    new_sms = SmsModel(income_sms=new_sms_data['income_sms'],
                                       user_id=user.id,
                                       status=0,
                                       status_time=datetime.now())
                    session.add(new_sms)
                    session.commit()
                    return flask.jsonify(new_sms.to_dict())
                else:
                    raise HTTPError(403, 'user is not found')
        else:
            raise HTTPError(403, 'no permission')

    # def delete(self, ads_id: int):
    #     with Session() as session:
    #         token = check_token(session)
    #         ads = session.query(AdsModel).filter(AdsModel.id == ads_id).first()
    #         if token.user.id != ads.user_id:
    #             raise HTTPError(403, "auth error")
    #         else:
    #             for_del = session.query(AdsModel).get(ads_id)
    #             session.delete(for_del)
    #             session.commit()
    #             return flask.jsonify({'result': f'Ads {ads_id} deleted'})
    #
    # def patch(self, ads_id: int):
    #     with Session() as session:
    #         token = check_token(session)
    #         ads = session.query(AdsModel).filter(AdsModel.id == ads_id).first()
    #         if token.user.id != ads.user_id:
    #             raise HTTPError(403, "auth error")
    #         else:
    #             session.query(AdsModel).filter(AdsModel.id == ads_id).update(request.json)
    #             session.commit()
    #             upd_ads = session.query(AdsModel).get(ads_id)
    #             return flask.jsonify(upd_ads.to_dict())


app.add_url_rule('/user/<int:user_id>/', view_func=UserView.as_view('get_user'), methods=['GET'])
app.add_url_rule('/create_user/', view_func=UserView.as_view('create_user'), methods=['POST'])
app.add_url_rule('/user/', view_func=AllUserView.as_view('get_users'), methods=['GET'])
app.add_url_rule('/sms/', view_func=AllSmsView.as_view('get_sms'), methods=['GET'])
app.add_url_rule('/create_sms/', view_func=SmsView.as_view('create_sms'), methods=['POST'])
app.add_url_rule('/sms/<int:ads_id>/', view_func=SmsView.as_view('delete_sms'), methods=['DELETE'])
app.add_url_rule('/sms/<int:ads_id>/', view_func=SmsView.as_view('patch_sms'), methods=['PATCH'])
app.add_url_rule('/sms/<int:ads_id>/', view_func=SmsView.as_view('view_sms'), methods=['GET'])
