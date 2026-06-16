// 曹义德律师 - 法律文库 VuePress 配置
// 基于 JustLaws 官方源配置二次定制（删除 Algolia 外网搜索/版权外链/ImCaO 署名）
const { defaultTheme } = require("@vuepress/theme-default");
const { searchPlugin } = require("@vuepress/plugin-search");
const { categoryNavbarItem } = require("./category-navigation");

module.exports = {
  lang: "zh-CN",
  title: "法律文库",
  description: "收录 308 部现行有效法律 - 曹义德律师",
  // 关键：部署到子路径 /laws/，所有资源链接前加 /laws/
  base: "/laws/",
  head: [
    ["link", { rel: "icon", href: "/images/logo.png" }],
  ],

  theme: defaultTheme({
    logo: "/images/logo.png",
    navbar: [
      {
        text: "全部类别",
        link: "/category/",
      },
      {
        text: "宪法",
        children: [
          { text: "宪法", link: "/constitution/", activeMatch: "/constitution/[^(amendment)]" },
          { text: "宪法修正案", link: "/constitution/amendment/" },
        ],
      },
      categoryNavbarItem({
        text: "宪法相关法",
        slug: "constitutional-relevance",
        featured: [
          "全国人民代表大会组织法",
          "民族区域自治法",
          "香港特别行政区基本法",
        ],
      }),
      categoryNavbarItem({
        text: "民商法",
        slug: "civil-and-commercial",
        featured: [
          "民法典",
        ],
      }),
      categoryNavbarItem({
        text: "行政法",
        slug: "administrative",
        featured: [
          "行政处罚法",
        ],
      }),
      categoryNavbarItem({
        text: "经济法",
        slug: "economic",
        featured: [
          "反垄断法",
        ],
      }),
      categoryNavbarItem({
        text: "刑法",
        slug: "criminal-law",
        children: [
          { text: "中华人民共和国刑法", link: "/criminal-law/criminal-law/" },
          { text: "刑法修正案", link: "/criminal-law/amendment/" },
        ],
      }),
      categoryNavbarItem({
        text: "程序法",
        slug: "procedural",
        featured: [
          "民事诉讼法",
        ],
      }),
      categoryNavbarItem({
        text: "社会法",
        slug: "social",
        featured: [
        ],
      }),
    ],
    sidebar: {
      "/constitution/": [
        {
          text: "中华人民共和国宪法",
          children: [
            "/constitution/preamble.md",
            "/constitution/01-general-principles.md",
            "/constitution/02-civil-rights-and-duties.md",
            "/constitution/03-state-institutions.md",
            "/constitution/04-flag-anthem-emblem-capital.md",
          ],
        },
      ],
      "/criminal-law/criminal-law/": [
        {
          text: "中华人民共和国刑法",
          children: [
            "/criminal-law/criminal-law/01-general-provisions.md",
            "/criminal-law/criminal-law/02-specific-provisions.md",
            "/criminal-law/criminal-law/00-supplementary.md",
          ],
        },
      ],
      "/criminal-law/amendment/": [
        {
          text: "刑法修正案",
          children: [
            "/criminal-law/amendment/criminal-law-amendment-i.md",
            "/criminal-law/amendment/criminal-law-amendment-ii.md",
            "/criminal-law/amendment/criminal-law-amendment-iii.md",
            "/criminal-law/amendment/criminal-law-amendment-iv.md",
            "/criminal-law/amendment/criminal-law-amendment-v.md",
            "/criminal-law/amendment/criminal-law-amendment-vi.md",
            "/criminal-law/amendment/criminal-law-amendment-vii.md",
            "/criminal-law/amendment/criminal-law-amendment-viii.md",
            "/criminal-law/amendment/criminal-law-amendment-ix.md",
            "/criminal-law/amendment/criminal-law-amendment-x.md",
            "/criminal-law/amendment/criminal-law-amendment-xi.md",
          ],
        },
      ],
      "/procedural/criminal-procedure/": [
        {
          text: "中华人民共和国刑事诉讼法",
          children: [
            "/procedural/criminal-procedure/01-general-provisions.md",
            "/procedural/criminal-procedure/02-filing-investigation-prosecution.md",
            "/procedural/criminal-procedure/03-trial.md",
            "/procedural/criminal-procedure/04-enforcement.md",
            "/procedural/criminal-procedure/05-special-procedures.md",
            "/procedural/criminal-procedure/00-supplementary.md",
          ],
        },
      ],
      "/procedural/civil-procedure/": [
        {
          text: "中华人民共和国民事诉讼法",
          children: [
            "/procedural/civil-procedure/01-general-provisions.md",
            "/procedural/civil-procedure/02-trial-procedure.md",
            "/procedural/civil-procedure/03-execution-procedure.md",
            "/procedural/civil-procedure/04-special-provisions-for-foreign-related-civil-procedure.md",
          ],
        },
      ],
      "/civil-and-commercial/civil-code/": [
        {
          text: "中华人民共和国民法典",
          children: [
            "/civil-and-commercial/civil-code/01-general-principles.md",
            "/civil-and-commercial/civil-code/02-property-rights.md",
            "/civil-and-commercial/civil-code/03-contracts.md",
            "/civil-and-commercial/civil-code/04-personality-rights.md",
            "/civil-and-commercial/civil-code/05-marriage-and-family.md",
            "/civil-and-commercial/civil-code/06-inheritance.md",
            "/civil-and-commercial/civil-code/07-tort-liability.md",
            "/civil-and-commercial/civil-code/00-supplementary.md",
          ],
        },
      ],
    },
    // 删除外链版权
    repo: undefined,
    docsRepo: undefined,
    docsBranch: undefined,
    docsDir: undefined,
    editLinkText: undefined,
    contributors: false,
    lastUpdated: true,
    lastUpdatedText: "上次更新",
    notFound: ["页面未找到"],
    backToHome: "回到主页",
    toggleColorMode: "切换夜间模式",
    toggleSidebar: "切换侧边栏",
  }),

  // 用本地搜索（不依赖 Algolia 公网服务）
  plugins: [
    searchPlugin({
      locales: {
        "/": {
          placeholder: "搜索法律",
          translations: {
            button: {
              buttonText: "搜索法律",
              buttonAriaLabel: "搜索法律",
            },
          },
        },
      },
    }),
  ],
};
