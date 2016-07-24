# Xtrade: 极速股票交易模拟app

## 为什么要写这样一个软件

巧合, 幸运.

首先, 这是一个没有接触过的领域. 此前我一直排斥花时间去玩股票,所以对它一无所知. 但是, 当开始尝试写这个软件的时候,
此前一直存在于我脑海里的疑问, 再次弹出来了, 这次必须解决了. 这个问题就是: ``股票的价格是如何确定的?`` .再经过 Google和
同学的帮助, 不过还是 ``知乎`` 上的一个解答, 让我焕然大悟了.开心!!!!

其次, 感觉这个系统可以采用 ``CQRS`` 来写, 或者说是 ``事件朔源`` . 之前, Chris Richardson介绍的这个神奇的
解决方案. 可以让交易的处理速度大大提升,同时可以根据不同的需求, 定制不同的输出.最后, 所有的事件已经被原生的记录了下来,
可以追查,分析等等.

不过, 现在,我还没有实现事件回放.

## 如何使用

### 初始化virtualenv环境及安装package

* 建议使用pyenv安装并创建virtualenv
* 当前只支持``python3``
* 安装依赖包: pip install -r requirements

### 启动服务

执行如下命令启动
```
$ cd xtran
$ export PYTHONPATH=$(pwd)
$ python -m xtran.app
```

如果正常启动,则应该有如下输出

```
INFO:werkzeug: * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

当前可以通过观察一下日志文件:

* depth.log: 等待交易的订单列表
* order.log: 执行交易的订单记录
* trade.log: 交易记录

### 运行模拟客户端
执行如下命令开始测试:

```
$ python test_client.py
```

## TEST

```
$ pip install -r requirements
$ py.test tests/ -v -s
```

## Todo

* 数据写入数据库
* 事件回放
* web页面: 可以执行买卖, 实时展示股价走势

