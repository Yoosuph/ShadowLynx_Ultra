import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
from flask import render_template, jsonify, request, redirect, url_for, send_file, flash
import pandas as pd
import io
from api.app import app, db
from models import ArbitrageOpportunity, ArbitrageExecution, TokenPrice, SystemStatus, ProfitSummary, AIAnalysis
from ai.agent import AIAgent

logger = logging.getLogger(__name__)
ai_agent = AIAgent()

# Create database tables if not exists (using init_app function)
def init_db():
    try:
        with app.app_context():
            db.create_all()
            logger.info("Database tables created (if they didn't exist already)")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

# Initialize database
init_db()

# Helper function to run async functions
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(coro)
    loop.close()
    return result

# Dashboard route
@app.route('/')
def dashboard():
    """Main dashboard page"""
    # Create default context with empty values
    context = {
        'system_status': {},
        'profit_summary': None,
        'recent_opportunities': [],
        'recent_executions': [],
        'total_profit': 0,
        'total_transactions': 0,
        'success_rate': 0,
        'price_data': json.dumps({}),
        'error': None
    }
    
    try:
        # Get system status
        try:
            status_records = SystemStatus.query.all()
            context['system_status'] = {record.service_name: record.status for record in status_records}
        except Exception as e:
            logger.warning(f"Could not get system status: {str(e)}")
        
        # Get profit summary
        try:
            profit_summary = ProfitSummary.query.order_by(ProfitSummary.date.desc()).first()
            context['profit_summary'] = profit_summary
        except Exception as e:
            logger.warning(f"Could not get profit summary: {str(e)}")
        
        # Get recent opportunities
        try:
            recent_opportunities = ArbitrageOpportunity.query.order_by(
                ArbitrageOpportunity.created_at.desc()
            ).limit(10).all()
            context['recent_opportunities'] = recent_opportunities
        except Exception as e:
            logger.warning(f"Could not get recent opportunities: {str(e)}")
        
        # Get recent executions
        try:
            recent_executions = db.session.query(
                ArbitrageExecution, ArbitrageOpportunity
            ).join(
                ArbitrageOpportunity, 
                ArbitrageExecution.opportunity_id == ArbitrageOpportunity.id
            ).order_by(
                ArbitrageExecution.executed_at.desc()
            ).limit(10).all()
            context['recent_executions'] = recent_executions
        except Exception as e:
            logger.warning(f"Could not get recent executions: {str(e)}")
        
        # Calculate summary stats
        try:
            total_profit = db.session.query(db.func.sum(ArbitrageExecution.net_profit_usd)).scalar() or 0
            total_transactions = db.session.query(db.func.count(ArbitrageExecution.id)).scalar() or 0
            success_count = db.session.query(db.func.count(ArbitrageExecution.id)).filter(
                ArbitrageExecution.status == 'success'
            ).scalar() or 0
            
            success_rate = (success_count / total_transactions * 100) if total_transactions > 0 else 0
            
            context['total_profit'] = total_profit
            context['total_transactions'] = total_transactions
            context['success_rate'] = success_rate
        except Exception as e:
            logger.warning(f"Could not calculate summary statistics: {str(e)}")
        
        # Get token prices for charts
        try:
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            token_prices = TokenPrice.query.filter(
                TokenPrice.timestamp > one_day_ago
            ).order_by(TokenPrice.timestamp.asc()).all()
            
            # Group token prices by symbol for charting
            price_data = {}
            for price in token_prices:
                if price.token_symbol not in price_data:
                    price_data[price.token_symbol] = []
                
                price_data[price.token_symbol].append({
                    'timestamp': int(price.timestamp.timestamp() * 1000),
                    'price': price.price_usd,
                    'dex': price.dex_name
                })
            
            context['price_data'] = json.dumps(price_data)
        except Exception as e:
            logger.warning(f"Could not get price data: {str(e)}")
        
        return render_template('dashboard.html', **context)
    
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        context['error'] = f"Error loading dashboard data: {str(e)}"
        return render_template('dashboard.html', **context)

# Opportunities route
@app.route('/opportunities')
def opportunities():
    """View arbitrage opportunities"""
    try:
        # Get filter parameters
        network = request.args.get('network')
        min_profit = request.args.get('min_profit', type=float)
        source_dex = request.args.get('source_dex')
        target_dex = request.args.get('target_dex')
        token_pair = request.args.get('token_pair')
        
        # Base query
        query = ArbitrageOpportunity.query
        
        # Apply filters
        if network:
            query = query.filter(ArbitrageOpportunity.network == network)
        if min_profit:
            query = query.filter(ArbitrageOpportunity.estimated_profit_usd >= min_profit)
        if source_dex:
            query = query.filter(ArbitrageOpportunity.source_dex == source_dex)
        if target_dex:
            query = query.filter(ArbitrageOpportunity.target_dex == target_dex)
        if token_pair:
            query = query.filter(ArbitrageOpportunity.token_pair == token_pair)
            
        # Get distinct filter options for dropdowns
        networks = db.session.query(ArbitrageOpportunity.network).distinct().all()
        networks = [n[0] for n in networks]
        
        dexes = []
        source_dexes = db.session.query(ArbitrageOpportunity.source_dex).distinct().all()
        target_dexes = db.session.query(ArbitrageOpportunity.target_dex).distinct().all()
        dexes = list(set([d[0] for d in source_dexes] + [d[0] for d in target_dexes]))
        
        token_pairs = db.session.query(ArbitrageOpportunity.token_pair).distinct().all()
        token_pairs = [t[0] for t in token_pairs]
        
        # Paginate results
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        paginated_opportunities = query.order_by(
            ArbitrageOpportunity.created_at.desc()
        ).paginate(page=page, per_page=per_page)
        
        return render_template('opportunities.html',
                              opportunities=paginated_opportunities,
                              networks=networks,
                              dexes=dexes,
                              token_pairs=token_pairs,
                              network=network,
                              min_profit=min_profit,
                              source_dex=source_dex,
                              target_dex=target_dex,
                              token_pair=token_pair)
    
    except Exception as e:
        logger.error(f"Error in opportunities route: {str(e)}")
        return render_template('opportunities.html', 
                              error=f"Error loading opportunities: {str(e)}",
                              opportunities=None,
                              networks=[],
                              dexes=[],
                              token_pairs=[])

# System status route
@app.route('/status')
def status():
    """View system status and configuration"""
    try:
        # Get system status
        status_records = SystemStatus.query.all()
        
        # Get configuration
        from utils.config import load_config
        config = load_config()
        # Remove sensitive info
        if 'api_keys' in config:
            config['api_keys'] = {k: '****' if v else None for k, v in config['api_keys'].items()}
        
        # Format for display
        formatted_config = json.dumps(config, indent=2, default=str)
        
        # Get DB stats
        opportunity_count = db.session.query(db.func.count(ArbitrageOpportunity.id)).scalar() or 0
        execution_count = db.session.query(db.func.count(ArbitrageExecution.id)).scalar() or 0
        token_price_count = db.session.query(db.func.count(TokenPrice.id)).scalar() or 0
        
        return render_template('status.html',
                              status_records=status_records,
                              config=formatted_config,
                              opportunity_count=opportunity_count,
                              execution_count=execution_count,
                              token_price_count=token_price_count)
    
    except Exception as e:
        logger.error(f"Error in status route: {str(e)}")
        return render_template('status.html', 
                              error=f"Error loading system status: {str(e)}",
                              status_records=[],
                              config="{}")

# API Routes

@app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint for system status"""
    try:
        status_records = SystemStatus.query.all()
        result = []
        
        for record in status_records:
            result.append({
                'service_name': record.service_name,
                'status': record.status,
                'last_check': record.last_check.isoformat() if record.last_check else None,
                'uptime_seconds': record.uptime_seconds,
                'response_time_ms': record.response_time_ms,
                'error_count': record.error_count,
                'details': record.details
            })
            
        return jsonify({
            'success': True,
            'status': result
        })
    
    except Exception as e:
        logger.error(f"Error in API status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/opportunities', methods=['GET'])
def api_opportunities():
    """API endpoint for arbitrage opportunities"""
    try:
        # Get filter parameters
        network = request.args.get('network')
        min_profit = request.args.get('min_profit', type=float)
        limit = request.args.get('limit', 100, type=int)
        
        # Base query
        query = ArbitrageOpportunity.query
        
        # Apply filters
        if network:
            query = query.filter(ArbitrageOpportunity.network == network)
        if min_profit:
            query = query.filter(ArbitrageOpportunity.estimated_profit_usd >= min_profit)
            
        # Execute query
        opportunities = query.order_by(
            ArbitrageOpportunity.created_at.desc()
        ).limit(limit).all()
        
        # Format results
        result = []
        for op in opportunities:
            result.append({
                'id': op.id,
                'token_pair': op.token_pair,
                'source_dex': op.source_dex,
                'target_dex': op.target_dex,
                'source_price': op.source_price,
                'target_price': op.target_price,
                'price_difference_percent': op.price_difference_percent,
                'estimated_profit_usd': op.estimated_profit_usd,
                'network': op.network,
                'flash_loan_provider': op.flash_loan_provider,
                'loan_amount': op.loan_amount,
                'created_at': op.created_at.isoformat() if op.created_at else None,
                'ai_confidence': op.ai_confidence,
                'is_executed': op.is_executed
            })
            
        return jsonify({
            'success': True,
            'opportunities': result,
            'count': len(result)
        })
    
    except Exception as e:
        logger.error(f"Error in API opportunities: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/profits', methods=['GET'])
def api_profits():
    """API endpoint for profit data"""
    try:
        # Get filter parameters
        days = request.args.get('days', 30, type=int)
        
        # Get daily profit summaries
        start_date = datetime.utcnow() - timedelta(days=days)
        
        summaries = ProfitSummary.query.filter(
            ProfitSummary.date >= start_date
        ).order_by(ProfitSummary.date.asc()).all()
        
        # Format results
        result = []
        for summary in summaries:
            result.append({
                'date': summary.date.isoformat(),
                'total_profit_usd': summary.total_profit_usd,
                'total_transactions': summary.total_transactions,
                'success_rate': summary.success_rate,
                'avg_profit_per_trade': summary.avg_profit_per_trade,
                'most_profitable_pair': summary.most_profitable_pair,
                'total_gas_spent': summary.total_gas_spent,
                'total_flash_loan_fees': summary.total_flash_loan_fees
            })
            
        return jsonify({
            'success': True,
            'profits': result,
            'days': days,
            'total_profit': sum(s.total_profit_usd for s in summaries)
        })
    
    except Exception as e:
        logger.error(f"Error in API profits: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# AI Insights route
@app.route('/ai-insights')
def ai_insights():
    """View AI insights and analyses"""
    try:
        # Get recent opportunities for the modal
        recent_opportunities = ArbitrageOpportunity.query.order_by(
            ArbitrageOpportunity.created_at.desc()
        ).limit(20).all()
        
        # Get recent opportunity analyses
        opportunity_analyses = AIAnalysis.query.filter_by(
            analysis_type='opportunity'
        ).order_by(AIAnalysis.timestamp.desc()).limit(10).all()
        
        # Get recent market analyses
        market_analyses = AIAnalysis.query.filter_by(
            analysis_type='market'
        ).order_by(AIAnalysis.timestamp.desc()).limit(5).all()
        
        # Get recent strategy optimizations
        strategy_analyses = AIAnalysis.query.filter_by(
            analysis_type='strategy'
        ).order_by(AIAnalysis.timestamp.desc()).limit(5).all()
        
        return render_template('ai_insights.html',
                             recent_opportunities=recent_opportunities,
                             opportunity_analyses=opportunity_analyses,
                             market_analyses=market_analyses,
                             strategy_analyses=strategy_analyses)
    
    except Exception as e:
        logger.error(f"Error in AI insights route: {str(e)}")
        return render_template('ai_insights.html',
                             error=f"Error loading AI insights: {str(e)}",
                             recent_opportunities=[],
                             opportunity_analyses=[],
                             market_analyses=[],
                             strategy_analyses=[])

@app.route('/analyze-opportunity', methods=['POST'])
def analyze_opportunity():
    """Analyze an arbitrage opportunity with AI"""
    try:
        opportunity_id = request.form.get('opportunity_id', type=int)
        
        if not opportunity_id:
            return redirect(url_for('ai_insights'))
        
        # Get the opportunity
        opportunity = ArbitrageOpportunity.query.get(opportunity_id)
        if not opportunity:
            flash('Opportunity not found', 'error')
            return redirect(url_for('ai_insights'))
        
        # Convert to dict for analysis
        opportunity_data = {
            'id': opportunity.id,
            'token_pair': opportunity.token_pair,
            'source_dex': opportunity.source_dex,
            'target_dex': opportunity.target_dex,
            'source_price': opportunity.source_price,
            'target_price': opportunity.target_price,
            'price_difference_percent': opportunity.price_difference_percent,
            'estimated_profit_usd': opportunity.estimated_profit_usd,
            'network': opportunity.network,
            'flash_loan_provider': opportunity.flash_loan_provider,
            'loan_amount': opportunity.loan_amount,
            'created_at': opportunity.created_at.isoformat() if opportunity.created_at else None,
            'ai_confidence': opportunity.ai_confidence
        }
        
        # Run the AI analysis
        result = run_async(ai_agent.analyze_opportunity(opportunity_data))
        
        # Store the analysis result
        analysis = AIAnalysis(
            opportunity_id=opportunity.id,
            analysis_type='opportunity',
            content=result,
            success_probability=result.get('success_probability'),
            risk_score=result.get('risk_score'),
            strategy_recommendation=result.get('strategy_recommendation'),
            profitability_impact=result.get('profitability_impact'),
            request_parameters={'opportunity_id': opportunity_id}
        )
        db.session.add(analysis)
        db.session.commit()
        
        # Update the opportunity's AI confidence if provided
        if 'success_probability' in result:
            opportunity.ai_confidence = result['success_probability']
            db.session.commit()
        
        flash('AI analysis completed successfully', 'success')
        return redirect(url_for('ai_insights'))
    
    except Exception as e:
        logger.error(f"Error analyzing opportunity: {str(e)}")
        flash(f"Error during analysis: {str(e)}", 'error')
        return redirect(url_for('ai_insights'))

@app.route('/generate-market-insights', methods=['POST'])
def generate_market_insights():
    """Generate market insights with AI"""
    try:
        token_pairs = request.form.get('token_pairs', '')
        timeframe = request.form.get('timeframe', '24h')
        
        # Parse token pairs
        tokens = [pair.strip() for pair in token_pairs.split(',') if pair.strip()]
        
        if not tokens:
            flash('Please provide at least one token pair', 'error')
            return redirect(url_for('ai_insights'))
        
        # Run the AI analysis
        result = run_async(ai_agent.generate_market_insights(tokens, timeframe))
        
        # Store the analysis result
        analysis = AIAnalysis(
            analysis_type='market',
            content=result,
            tokens_analyzed=token_pairs,
            request_parameters={'token_pairs': tokens, 'timeframe': timeframe}
        )
        db.session.add(analysis)
        db.session.commit()
        
        flash('Market insights generated successfully', 'success')
        return redirect(url_for('ai_insights'))
    
    except Exception as e:
        logger.error(f"Error generating market insights: {str(e)}")
        flash(f"Error generating insights: {str(e)}", 'error')
        return redirect(url_for('ai_insights'))

@app.route('/optimize-strategy', methods=['POST'])
def optimize_strategy():
    """Optimize trading strategy with AI"""
    try:
        timeperiod = request.form.get('timeperiod', '30d')
        params = request.form.to_dict().get('params', {})
        
        # If params is a string (due to form encoding), convert to dict
        if isinstance(params, str):
            params = {k: v for k, v in request.form.items() if k.startswith('params[')}
        
        # Get historical data
        end_date = datetime.utcnow()
        
        if timeperiod == '7d':
            start_date = end_date - timedelta(days=7)
        elif timeperiod == '90d':
            start_date = end_date - timedelta(days=90)
        else:  # default to 30d
            start_date = end_date - timedelta(days=30)
        
        # Get execution statistics
        executions = ArbitrageExecution.query.filter(
            ArbitrageExecution.executed_at >= start_date
        ).all()
        
        # Prepare historical data
        historical_data = {
            'period': timeperiod,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_executions': len(executions),
            'successful_executions': sum(1 for e in executions if e.status == 'success'),
            'failed_executions': sum(1 for e in executions if e.status == 'failed'),
            'total_profit': sum(e.net_profit_usd for e in executions if e.net_profit_usd),
            'average_profit': sum(e.net_profit_usd for e in executions if e.net_profit_usd) / len([e for e in executions if e.net_profit_usd]) if any(e.net_profit_usd for e in executions) else 0,
            'average_gas_cost': sum(e.gas_cost_usd for e in executions if e.gas_cost_usd) / len([e for e in executions if e.gas_cost_usd]) if any(e.gas_cost_usd for e in executions) else 0,
            'networks': {
                'BSC': sum(1 for e in executions if e.opportunity and e.opportunity.network == 'BSC'),
                'Polygon': sum(1 for e in executions if e.opportunity and e.opportunity.network == 'Polygon')
            }
        }
        
        # Run the AI analysis
        result = run_async(ai_agent.optimize_strategy(historical_data, params))
        
        # Store the analysis result
        analysis = AIAnalysis(
            analysis_type='strategy',
            content=result,
            request_parameters={'timeperiod': timeperiod, 'current_params': params}
        )
        db.session.add(analysis)
        db.session.commit()
        
        flash('Strategy optimization completed successfully', 'success')
        return redirect(url_for('ai_insights'))
    
    except Exception as e:
        logger.error(f"Error optimizing strategy: {str(e)}")
        flash(f"Error during strategy optimization: {str(e)}", 'error')
        return redirect(url_for('ai_insights'))

@app.route('/api/export-csv', methods=['GET'])
def export_csv():
    """Export data as CSV"""
    try:
        export_type = request.args.get('type', 'opportunities')
        days = request.args.get('days', 30, type=int)
        
        # Get data based on type
        start_date = datetime.utcnow() - timedelta(days=days)
        
        if export_type == 'opportunities':
            # Export opportunities
            opportunities = ArbitrageOpportunity.query.filter(
                ArbitrageOpportunity.created_at >= start_date
            ).order_by(ArbitrageOpportunity.created_at.desc()).all()
            
            # Convert to DataFrame
            data = []
            for op in opportunities:
                data.append({
                    'id': op.id,
                    'token_pair': op.token_pair,
                    'source_dex': op.source_dex,
                    'target_dex': op.target_dex,
                    'source_price': op.source_price,
                    'target_price': op.target_price,
                    'price_difference_percent': op.price_difference_percent,
                    'estimated_profit_usd': op.estimated_profit_usd,
                    'network': op.network,
                    'flash_loan_provider': op.flash_loan_provider,
                    'loan_amount': op.loan_amount,
                    'created_at': op.created_at,
                    'ai_confidence': op.ai_confidence,
                    'is_executed': op.is_executed
                })
                
            df = pd.DataFrame(data)
            filename = f"arbitrage_opportunities_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            
        elif export_type == 'executions':
            # Export executions
            executions = db.session.query(
                ArbitrageExecution, ArbitrageOpportunity
            ).join(
                ArbitrageOpportunity, 
                ArbitrageExecution.opportunity_id == ArbitrageOpportunity.id
            ).filter(
                ArbitrageExecution.executed_at >= start_date
            ).order_by(ArbitrageExecution.executed_at.desc()).all()
            
            # Convert to DataFrame
            data = []
            for exec_record, op in executions:
                data.append({
                    'execution_id': exec_record.id,
                    'opportunity_id': op.id,
                    'token_pair': op.token_pair,
                    'source_dex': op.source_dex,
                    'target_dex': op.target_dex,
                    'transaction_hash': exec_record.transaction_hash,
                    'status': exec_record.status,
                    'estimated_profit_usd': op.estimated_profit_usd,
                    'actual_profit_usd': exec_record.actual_profit_usd,
                    'gas_cost_usd': exec_record.gas_cost_usd,
                    'net_profit_usd': exec_record.net_profit_usd,
                    'network': op.network,
                    'flash_loan_fee': exec_record.flash_loan_fee,
                    'executed_at': exec_record.executed_at,
                    'execution_time_ms': exec_record.execution_time_ms,
                    'error_message': exec_record.error_message
                })
                
            df = pd.DataFrame(data)
            filename = f"arbitrage_executions_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            
        else:
            return jsonify({
                'success': False,
                'error': f"Invalid export type: {export_type}"
            }), 400
            
        # Generate CSV
        csv_data = io.StringIO()
        df.to_csv(csv_data, index=False)
        csv_data.seek(0)
        
        return send_file(
            io.BytesIO(csv_data.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
