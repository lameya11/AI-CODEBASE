import React, { useState } from 'react';
import { fetchUsers } from './api';
import { validateEmail } from './utils';

function UserList({ title }) {
    const [users, setUsers] = useState([]);

    const loadUsers = async () => {
        const data = await fetchUsers();
        setUsers(data);
    };

    return (
        <div>
            <h1>{title}</h1>
            <ul>
                {users.map(u => <li key={u.id}>{u.name}</li>)}
            </ul>
        </div>
    );
}

export default UserList;
