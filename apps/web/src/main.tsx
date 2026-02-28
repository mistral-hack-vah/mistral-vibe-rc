import React from 'react';
import ReactDOM from 'react-dom/client';
import { greet } from '@thread/shared';

function App() {
  return (
    <div>
      <h1>{greet('Mistral Thread')}</h1>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
