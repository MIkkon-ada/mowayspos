# 离线上线验收清单

本文档用于 L5 阶段的离线上线验收准备。当前没有真实 Linux 服务器时，只能作为验收材料和执行模板，不能替代 L4-2S 真实服务器验证。

## 1. 服务器验证项

- [ ] 后端仓库工作区干净
- [ ] 前端仓库工作区干净
- [ ] `frontend/dist` 已构建并发布到服务器
- [ ] `/etc/bowei-ai-dashboard.env` 已就位
- [ ] `systemd-analyze verify /etc/systemd/system/bowei.service` 通过
- [ ] `systemctl status bowei` 正常
- [ ] `nginx -t` 通过
- [ ] `/api/health` 可访问

## 2. 登录 / 退出验收

- [ ] `POST /api/auth/login` 返回 200
- [ ] `Set-Cookie` 包含 `bowei_session`
- [ ] `HttpOnly` 已开启
- [ ] `SameSite=lax`
- [ ] HTTPS 生产环境下 `Secure` 已开启
- [ ] `GET /api/auth/me` 登录后返回 200
- [ ] `POST /api/auth/logout` 返回 200
- [ ] logout 后 `GET /api/auth/me` 返回 401

## 3. 角色菜单验收

角色覆盖（业务口径）：

- [ ] 公司 CEO
- [ ] 企业教练
- [ ] 项目负责人 / PM
- [ ] 项目统筹人
- [ ] 关键任务责任人
- [ ] 关键任务协助人

验收点：

- [ ] 各角色只看到自己应看到的菜单与入口
- [ ] 非授权角色不应看到管理入口
- [ ] 角色切换后页面与权限状态一致

## 4. 权限边界验收

- [ ] 项目负责人 / PM 可推进日常业务并确认入库
- [ ] 关键任务协助人不能越权执行责任人动作
- [ ] 项目统筹人只能处理协调类流程
- [ ] 企业教练只能处理重大事项和结束复盘把关类流程
- [ ] 公司 CEO 拥有全局查看和项目入口配置权限
- [ ] 最后一个项目负责人保护规则生效

## 5. 进展提交验收

- [ ] 进展提交可创建
- [ ] 进展提交可进入 AI 确认中心
- [ ] 项目负责人 / PM 可确认
- [ ] 项目统筹人和企业教练只能看到自己的待处理项

## 6. AI 确认中心验收

- [ ] `GET /api/confirmations/pending` 正常
- [ ] 已确认 / 转交 / CEO 决策流程正常
- [ ] 异常状态不会误导出到错误角色

## 7. 统筹建议 / 企业教练决策验收

- [ ] 转交给项目统筹人的记录仅由项目统筹人处理
- [ ] 转交给企业教练的记录仅由企业教练处理
- [ ] 决策结果可回传并可查询

## 8. Dashboard 首页风格冻结验收

- [ ] 首页布局未意外变更
- [ ] DashboardPage 风格与 L2/L3 冻结版本一致
- [ ] 视觉上无未授权改版

## 9. 备份 / 恢复验收

- [ ] `scripts/backup_db.sh` 可生成备份
- [ ] `scripts/restore_db.sh` 可恢复到临时库
- [ ] 恢复过程不覆盖正式库
- [ ] 备份 / 恢复 SOP 可执行

## 10. Cookie / secret / health check 验收

- [ ] `/api/health` 返回 200 且不暴露敏感信息
- [ ] `SESSION_COOKIE_SECURE` 与 HTTPS 配套
- [ ] `SESSION_COOKIE_SAMESITE=lax`
- [ ] `bowei_session` 名称保持不变
- [ ] auth / LLM secrets 通过环境变量外部化

## 11. 数据库 mtime / 防污染检查

- [ ] 正式库 mtime 在验收过程中未发生非预期变化
- [ ] 仅允许预期的 session 写入或验收写入
- [ ] 不允许直接对正式库跑写库回归

## 12. 上线阻塞项判断标准

以下任一项不通过，视为阻塞：

- [ ] Nginx 配置错误
- [ ] `/api` 反代错误
- [ ] SPA fallback 404
- [ ] 登录态异常
- [ ] Cookie 安全属性不符合预期
- [ ] 正式库被污染
- [ ] 未完成备份 / 恢复演练

## 13. 备注

- 当前若无真实 Linux 服务器，只能完成文档准备和本地回归
- L4-2S 真实服务器验证未通过前，不应进入正式上线结论
