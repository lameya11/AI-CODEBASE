"""Tests for the JavaScript/TypeScript parser."""
import pytest
from app.core.parsers.js_parser import parse_js

ES_MODULE_SOURCE = """\
import express from 'express';
import { authMiddleware, logRequest } from './middleware';
import * as utils from '../utils';
const db = require('./database');

function greetUser(name) {
    return `Hello, ${name}`;
}

const fetchData = async (url) => {
    return await db.query(url);
};

const processRequest = function(req, res) {
    return greetUser(req.params.name);
};

class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }
}

const router = express.Router();
router.get('/users', async (req, res) => {
    res.json([]);
});
router.post('/login', async (req, res) => {
    res.json({token: 'x'});
});

export default router;
"""

JSX_SOURCE = """\
import React from 'react';
import { useState } from 'react';
import { fetchUsers } from './api';

function UserList({ title }) {
    const [users, setUsers] = useState([]);
    return (
        <div>
            <h1>{title}</h1>
        </div>
    );
}

export default UserList;
"""


def test_import_from():
    result = parse_js(ES_MODULE_SOURCE)
    modules = [i.module for i in result.imports]
    assert "express" in modules
    assert "./middleware" in modules
    assert "../utils" in modules


def test_require_import():
    result = parse_js(ES_MODULE_SOURCE)
    modules = [i.module for i in result.imports]
    assert "./database" in modules


def test_function_detection():
    result = parse_js(ES_MODULE_SOURCE)
    func_names = [s.name for s in result.symbols if s.kind in ("function", "component")]
    assert "greetUser" in func_names


def test_arrow_function_detection():
    result = parse_js(ES_MODULE_SOURCE)
    func_names = [s.name for s in result.symbols]
    assert "fetchData" in func_names


def test_class_detection():
    result = parse_js(ES_MODULE_SOURCE)
    class_names = [s.name for s in result.symbols if s.kind == "class"]
    assert "ApiClient" in class_names


def test_router_routes():
    result = parse_js(ES_MODULE_SOURCE)
    routes = [s for s in result.symbols if s.kind == "route"]
    assert len(routes) >= 2
    methods = {r.route_method for r in routes}
    paths = {r.route_path for r in routes}
    assert "GET" in methods
    assert "POST" in methods
    assert "/users" in paths
    assert "/login" in paths


def test_react_component_detection():
    result = parse_js(JSX_SOURCE, file_path="UserList.jsx")
    components = [s for s in result.symbols if s.kind == "component"]
    assert len(components) >= 1
    assert any(c.name == "UserList" for c in components)


def test_import_deduplication():
    source = """\
import React from 'react';
import React from 'react';
"""
    result = parse_js(source)
    react_imports = [i for i in result.imports if i.module == "react"]
    assert len(react_imports) == 1
