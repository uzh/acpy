#!/usr/bin/env python
# -*- coding: utf-8 -*-#
#
#
# Copyright (C) 2018 University of Zurich. All rights reserved.
#
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import logging

from connexion import NoContent
from flask import session
from sqlalchemy.exc import SQLAlchemyError

from api.admin import is_admin, is_group_admin
from api.auth import ensure_token
from db.group import Member, Group
from db.handler import db_session
from db.user import User

logger = logging.getLogger('api.group')


@ensure_token
def get_groups(active=False):
    """
    list all groups (admins only)
    :param active: only show active groups
    :return: list of group
    """
    if not is_admin():
        return NoContent, 401
    if active:
        groups = [g.dump() for g in db_session.query(Group).all() if g.active]
    else:
        groups = [g.dump() for g in db_session.query(Group).all()]
    return groups, 200


@ensure_token
def add_group(group):
    """
    add a group (admins only)
    :param group: group
    :return: group
    """
    if not is_admin():
        return NoContent, 401
    u = db_session.query(User).filter(User.dom_name == group['dom_name']).one_or_none()
    if not u:
        return "could not find user {0} for ownership".format(group['dom_name']), 404
    group.pop('dom_name', None)
    try:
        g = Group(**group, user_id=u.id)
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)
        return g.dump(), 201
    except SQLAlchemyError:
        logger.exception("error while creating group")
        return NoContent, 500


@ensure_token
def update_group(gid, group_update):
    """
    update a group (admins and group admins)
    :param gid: group id
    :param group_update: group
    :return: success or fail
    """
    if not is_group_admin(gid):
        return NoContent, 401
    group = db_session.query(Group).filter(Group.id == gid).one_or_none()
    group.pop('id', None)
    try:
        for k in group_update:
            setattr(group, k, group_update[k])
        db_session.commit()
        return NoContent, 200
    except SQLAlchemyError:
        logger.exception("error while updating group")
        return NoContent, 500


@ensure_token
def get_group_users(gid):
    """
    get users of a group (admins, group admins and members)
    :param gid: group id
    :return: list of user
    """
    if not is_admin():
        u = None
        if 'username' in session:
            u = db_session.query(User).filter(User.dom_name == session['username']).one_or_none()
        if not u or not db_session.query(Member).filter(Member.group_id == gid and Member.user_id == u.id).one_or_none():
            logger.warning("user {0} not found as part of group".format(session['username']))
            return NoContent, 401
    users = []
    for group_user in db_session.query(Member).filter(Member.group_id == gid).all():
        gu = db_session.query(User).filter(User.id == group_user.user_id).one_or_none()
        if gu:
            users.append(dict(dom_name=gu.dom_name, full_name=gu.full_name, admin=group_user.admin))
    return users, 200


@ensure_token
def add_group_user(gid, user, admin):
    """
    add user to group (admins and group admins)
    :param gid: group id
    :param user: dom_name
    :param admin: add as admin
    :return:
    """
    if not is_group_admin(gid):
        return NoContent, 401
    user = db_session.query(User).filter(User.dom_name == user).one_or_none()
    if not user:
        return 'User does not exist', 404
    group = db_session.query(Group).filter(Group.id == gid).one()
    try:
        db_session.add(Member(group=group, user=user, admin=admin))
        db_session.commit()
        return NoContent, 201
    except SQLAlchemyError:
        logger.exception("error while updating group")
        return NoContent, 500


@ensure_token
def remove_group_user(gid, user):
    """
    remove user from group (admins and group admins)
    :param gid: group id
    :param user: dom_name
    :return: success or failure
    """
    if not is_group_admin(gid):
        return NoContent, 401
    user = db_session.query(User).filter(User.dom_name == user).one_or_none()
    if not user:
        return 'User does not exist', 404
    group = db_session.query(Group).filter(Group.id == gid).one()
    try:
        db_session.query(Member).filter(Member.group == group and Member.user == user).delete()
        db_session.commit()
        return NoContent, 200
    except SQLAlchemyError:
        logger.exception("error while updating group")
        return NoContent, 500
