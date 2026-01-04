import { createApp } from 'vue';
import App from './App.vue';

const app = createApp(App);

// 全局样式
const globalStyles = `
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  line-height: 1.6;
  color: #333;
}

button {
  font-family: inherit;
}
`;

const styleEl = document.createElement('style');
styleEl.textContent = globalStyles;
document.head.appendChild(styleEl);

app.mount('#app');