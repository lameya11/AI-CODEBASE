import express from 'express';
import { authMiddleware } from './middleware';
import axios from 'axios';

const router = express.Router();

function greetUser(name) {
    return `Hello, ${name}!`;
}

const fetchData = async (url) => {
    const response = await axios.get(url);
    return response.data;
};

class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }
}

router.get('/users', authMiddleware, async (req, res) => {
    const users = await fetchData('/api/users');
    res.json(users);
});

router.post('/login', async (req, res) => {
    const { username, password } = req.body;
    res.json({ token: 'fake-token' });
});

export default router;
