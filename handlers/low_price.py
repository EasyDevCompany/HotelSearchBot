import re

from aiogram import types, Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils.markdown import hbold
from utils import rapid_hotels_api
from loader import bot
from keyboards import keyboards
from loguru import logger
from database import sqlite
from config import path

sql = sqlite.Sqlite(path)


class WaiteCityAndCount(StatesGroup):
    """
    Формируем класс,
    где будем хранить состояния
    """
    waite_city_state = State()
    waite_photo_answer = State()
    waite_photo_count = State()
    waite_date = State()
    waite_count_state = State()


async def started_low_price_2(message: types.Message):

    """
    Запрашиваем у пользователя название города,
    активация через команду /low_price
    :param message: types.Message
    :return: None
    """
    await message.answer('Напишите название города🏢:  ')
    await WaiteCityAndCount.waite_city_state.set()


async def started_low_price(callback_query: types.CallbackQuery):
    """
    Запрашиваем у пользователя название города,
    активация через инлайн клавиатуру
    :param callback_query: types.CallbackQuery
    :return: None
    """
    logger.info(f"Пользователь: {callback_query.from_user.username} смотрит low_price")
    await callback_query.message.edit_text('Напишите название города🏢:  ')
    await callback_query.message.edit_reply_markup(reply_markup=keyboards.inline_buttons_3)
    await WaiteCityAndCount.waite_city_state.set()


async def waite_city_state(message: types.Message, state: FSMContext):
    """
    Проверка на корректность города,
    запрашиваем у пользователя необходимость фотографий
    сохраняем город в словарь
    :param message: types.Message
    :param state: FSMContext
    :return: None
    """
    if not message.text.isdigit():
        await state.update_data(city=message.text)
        await message.answer('Вам показать фотографии найденных отелей ?', reply_markup=keyboards.inline_buttons_2)
        await WaiteCityAndCount.waite_photo_answer.set()
    else:
        await message.answer('Введите город буквами!')


async def waite_photo_state(callback_query: types.CallbackQuery, state: FSMContext):
    """
    В зависимости от ответа пользователя запрашиваем кол-во фото или кол-во отелей,
    так же переходим к следующему состоянию в зависимости от ответа
    :param callback_query: types.CallbackQuery
    :param state: FSMContext
    :return: None
    """
    await callback_query.message.edit_reply_markup()
    photo_data = callback_query.data
    await state.update_data(photo=photo_data)
    if photo_data == 'yes':
        await callback_query.message.answer('Сколько фото вам показать?', reply_markup=keyboards.inline_buttons_4)
        await WaiteCityAndCount.waite_photo_count.set()
    else:
        await WaiteCityAndCount.waite_date.set()
        await callback_query.message.answer('Введите дату заселения и дату выезда как в примере'
                                            f'{hbold("ДД.ММ.ГГ-ДД.ММ.ГГ")}', reply_markup=keyboards.inline_buttons_4)


async def waite_count_photo_state(message: types.Message,  state: FSMContext):
    """
    Запрашиваем у пользователя кол-во отелей,
    проверяем на корректность,
    сохраняем кол-во фото в словарь,
    если пользователь ответил положительно
    :param message: types.Message
    :param state: FSMContext
    :return: None
    """
    if message.text.isdigit():
        await message.answer('Введите дату заселения и дату выезда как в примере'
                             f'{hbold("ДД.ММ.ГГ-ДД.ММ.ГГ")}', reply_markup=keyboards.inline_buttons_4)
        await state.update_data(count_photo=message.text)
        await WaiteCityAndCount.waite_date.set()


async def waite_date(message: types.Message, state: FSMContext):
    """
    Принимаем дату, проверяем ее на корректность,
    запрашиваем у пользователя кол-во отелей.
    :param message: types.Message
    :param state: FSMContext
    :return: None
    """
    date = re.findall(r"[0-9]*?[0-9]+", message.text)
    logger.info(date)
    if ((len(date) == 6) and (date is not None)
            and (int(date[1]) <= int(date[4])) and (int(date[2]) <= int(date[5]))):
        logger.info('Дата сохранена!')
        await message.answer('Сколько отелей вам показать?', reply_markup=keyboards.inline_buttons_4)
        await state.update_data(date=date)
        await WaiteCityAndCount.waite_count_state.set()
    else:
        await message.answer('Дата введена некорректно!')


async def watch_hotels(message: types.Message, state: FSMContext):
    """
    Проверяем на корректность введенные данные,
    отправляем пользователю все найденные отели,
    которые соответствуют параметрам
    :param message: types.Message
    :param state: FSMContext
    :return: None
    """
    person_id = message.from_user.id
    if message.text.isdigit():
        await state.update_data(count=message.text)
        user_data = await state.get_data()
        logger.info(f"Выбор пользователя {message.from_user.username}:"
                    f" {user_data['city']}, {user_data['photo']}, {message.text}")
        await message.answer('Идет поиск, подождите пару секунд...⌛️')
        history_dict = {"city": None, "search_results": []}
        try:
            full_info = rapid_hotels_api.get_id(user_data["city"], "PRICE")
            history_dict["city"] = full_info[1]
            return_info = full_info[0]["data"]["body"]["searchResults"]["results"]
            for index in range(0, int(user_data["count"])):
                price = (((int(user_data["date"][0]) + int(user_data["date"][3])) +
                         (30 * (int(user_data["date"][4]) - int(user_data["date"][1]))))
                         * return_info[index]["ratePlan"]["price"]["exactCurrent"])
                answer = (f'{hbold(return_info[index]["name"])}'
                          f'\n\nАдрес:  {return_info[index]["address"]["streetAddress"]}'
                          f'\nРасстояние до центра:  {return_info[index]["landmarks"][0]["distance"]}'
                          f'\nРейтинг:  {return_info[index]["starRating"]}'
                          f'\nЦена за указанный вами период:  {round(price, 2)}RUB')
                history_dict["search_results"].append(answer)
                await message.answer(answer)
                if user_data["photo"] == 'yes':
                    try:
                        for i in range(0, int(user_data["count_photo"])):
                            await bot.send_photo(person_id,
                                                 rapid_hotels_api.get_photo(return_info[index]["id"])
                                                 ["hotelImages"][i]["baseUrl"].format(
                                                    size="z"
                                                    ))
                    except TypeError as exc:
                        await message.answer('У данного отеля нету фотографий или мы не смогли его найти')
                        logger.error(f'Ошибка: {exc}')
        except (IndexError, KeyError) as exc:
            await state.finish()
            await message.answer('Это все, что нам удалось найти!')
            logger.error(f"Возникла ошибка: {exc}")
        await state.finish()
        sql.add_history(person_id, history_dict)
    else:
        await message.answer('Введите цифрами!')


def register_handlers_low_price(dp: Dispatcher):
    """
    Регистрация handlers
    :param dp: Dispatcher
    :return: None
    """
    dp.register_message_handler(started_low_price_2, commands=['low_price'])
    dp.register_callback_query_handler(started_low_price, text='button2')
    dp.register_callback_query_handler(waite_photo_state, state=WaiteCityAndCount.waite_photo_answer)
    dp.register_message_handler(waite_count_photo_state, state=WaiteCityAndCount.waite_photo_count)
    dp.register_message_handler(waite_date, state=WaiteCityAndCount.waite_date)
    dp.register_message_handler(waite_city_state, state=WaiteCityAndCount.waite_city_state)
    dp.register_message_handler(watch_hotels, state=WaiteCityAndCount.waite_count_state)