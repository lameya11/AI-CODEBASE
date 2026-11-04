import React, { useState } from 'react';
import Login from './Login';

function App() {
  const [loggedIn, setLoggedIn] = useState(false);

  if (loggedIn) {
    return <div><h1>Welcome!</h1><p>You are logged in.</p></div>;
  }

  return (
    <div>
      <h1>Sample Fullstack App</h1>
      <Login onLoginSuccess={() => setLoggedIn(true)} />
    </div>
  );
}

export default App;
