import React from 'react';
import ReactDOM from 'react-dom/client';
import { greet } from '@hackathon/shared';

function App() {
  return (
    <div>
      <h1>{greet('Hackathon')}</h1>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
