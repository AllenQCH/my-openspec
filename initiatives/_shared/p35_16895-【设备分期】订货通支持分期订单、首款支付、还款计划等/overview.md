# 【设备分期】订货通支持分期订单、首款支付、还款计划等

需求号：`p35_16895`。

## 本次范围

本次只实现国内发票“票据中心待开票订单与线下开票”能力，包括蓝票/红票待开列表、蓝票线下开票、关联红票同步线下、管理端接口、数据权限和存量 Job 回归。

## 涉及服务

- `hsp-invoice`
- `center-hsp-invoice`
- `manager-hsp-invoice-receiver`
- `manager-hsp-invoice`
- `service-hsp-invoice-backend`
- `job-hsp-invoice`

## 非目标

- 磐石前端代码开发。
- 新推票逻辑。
- 未经确认的权限菜单路由和权限 SQL 执行。
- 合并主干、生产发布或生产数据操作。

## 事实来源

详细需求、设计、变更文件和测试记录以各服务 Binding 指向的项目内 OpenSpec 为准；中央 Initiative 只维护跨服务范围、状态和最终证据关系。
