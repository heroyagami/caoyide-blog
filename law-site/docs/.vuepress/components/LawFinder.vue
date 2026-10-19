<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useRouteLocale } from '@vuepress/client';
import { useSearchIndex } from '@vuepress/plugin-search/lib/client/composables/useSearchIndex';

const index = useSearchIndex();
const locale = useRouteLocale();
const router = useRouter();
const query = ref('');
const open = ref(false);
const active = ref(-1);
const field = ref(null);
const composing = ref(false);
const results = computed(() => {
  const words = query.value.trim().toLowerCase().split(/\s+/).filter(Boolean).slice(0, 6);
  if (!words.length) return [];
  const matches = [];
  for (const page of index.value) {
    if (page.pathLocale !== locale.value || page.path.includes('/category/') || page.path === '/') continue;
    const title = page.title.toLowerCase();
    if (words.every(word => title.includes(word))) {
      matches.push({path: page.path, title: page.title, header: '', score: 2});
      continue;
    }
    const visit = headers => {
      for (const header of headers || []) {
        if (words.every(word => (title + ' ' + header.title.toLowerCase()).includes(word))) {
          matches.push({path: page.path + '#' + header.slug, title: page.title, header: header.title, score: 1});
          return;
        }
        visit(header.children);
      }
    };
    visit(page.headers);
  }
  return matches.sort((a, b) => b.score - a.score).slice(0, 8);
});
const visible = computed(() => open.value && query.value.trim().length > 0);
const move = delta => {
  if (!results.value.length) return;
  active.value = active.value < 0 ? (delta < 0 ? results.value.length - 1 : 0) : (active.value + delta + results.value.length) % results.value.length;
  nextTick(() => document.getElementById('law-finder-option-' + active.value)?.scrollIntoView({block: 'nearest'}));
};
const go = () => {
  if (composing.value) return;
  const result = results.value[Math.max(0, active.value)];
  if (result) { open.value = false; router.push(result.path); }
};
const shortcut = event => {
  if (event.target.closest('input,textarea,[contenteditable="true"]')) return;
  if (event.key === '/' || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k')) {
    event.preventDefault(); field.value?.focus();
  }
};
onMounted(() => document.addEventListener('keydown', shortcut));
onBeforeUnmount(() => document.removeEventListener('keydown', shortcut));
</script>

<template>
  <div class="law-finder" @focusout="event => { if (!event.currentTarget.contains(event.relatedTarget)) open = false }">
    <label for="law-finder-input">搜索法律名称或章节标题</label>
    <form role="search" aria-label="搜索法律文库" @submit.prevent="go">
      <input id="law-finder-input" ref="field" v-model="query" type="search" maxlength="100" placeholder="例如：民法典、劳动合同、行政处罚" autocomplete="off" role="combobox" aria-autocomplete="list" :aria-expanded="visible" aria-controls="visible ? 'law-finder-results' : undefined" :aria-activedescendant="visible && active >= 0 && results[active] ? 'law-finder-option-' + active : undefined" @focus="open = true" @input="open = true; active = -1" @compositionstart="composing = true" @compositionend="composing = false" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.esc.prevent="open = false; active = -1" />
      <button type="submit" aria-label="打开首个搜索结果">查找</button>
    </form>
    <div v-if="visible" class="law-finder-panel">
      <ul id="law-finder-results" role="listbox" aria-label="匹配的法律与章节">
        <li v-for="(result, position) in results" :key="result.path" role="none">
          <RouterLink :id="'law-finder-option-' + position" :to="result.path" role="option" :aria-selected="active === position" @mouseenter="active = position"><strong>{{ result.title }}</strong><span v-if="result.header">{{ result.header }}</span></RouterLink>
        </li>
      </ul>
      <p v-if="!results.length" role="status">没有找到，试试更短的法律名称或下方分类。</p>
    </div>
  </div>
</template>
